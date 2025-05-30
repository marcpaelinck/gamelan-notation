"""Formatting settings and instructions for the ScoreToPDFConverter.
The code uses the Platypus library of ReportLab.
See https://docs.reportlab.com/reportlab/userguide/ch5_platypus/.
"""

from __future__ import annotations

import html
from dataclasses import dataclass, field
from enum import Enum

from reportlab.lib import colors
from reportlab.lib.colors import HexColor
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.pdfbase.pdfmetrics import registerFont, stringWidth
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen.canvas import Canvas
from reportlab.platypus import (
    Frame,
    PageTemplate,
    Paragraph,
    SimpleDocTemplate,
    Table,
    TableStyle,
)

from src.notation2midi.metadata_classes import (
    DynamicsMeta,
    GoToMeta,
    LabelMeta,
    MetaData,
    PartMeta,
    RepeatMeta,
    SequenceMeta,
    TempoMeta,
)
from src.notation2midi.score2notation.utils import to_aggregated_tags
from src.settings.classes import RunSettings

# pylint: disable=no-member
# pylint: disable=invalid-name
# pylint: disable=missing-function-docstring


class SpanType(Enum):  # pylint: disable=missing-class-docstring
    RANGE = 1
    LAST_CELL = 2


class RowType(Enum):
    EMPTY = 0
    METADATA = 1
    COMMENT = 2
    NOTATION = 3


@dataclass(frozen=True)
class TableContent:
    """Convenience class that enables to build up the contents of a table
    row by row before creating an actual Table object.
    data: table-like list structure containing table data by row.
    style: TableStyle entries, see https://docs.reportlab.com/reportlab/userguide/ch7_tables/#tablestyle-line-commands
    colwidths: width of each column in points. len(colWidths) should
               be equal to len(row) for each row in data.
    template: NotationTemplate object which specifies the formatting of the document.
    """

    data: list[list[str | Paragraph]] = field(default_factory=list)
    rowtypes: list[RowType] = field(default_factory=list)
    style: list[tuple] = field(default_factory=list)
    colwidths: list[float] = field(default_factory=list)  # in pt
    rowheights: list[float] = field(default_factory=list)  # in pt
    template: NotationTemplate = None

    def __post__init__(self):
        if not len(self.data) == len(self.rowtypes) == len(self.rowheights):
            raise ValueError("Number of elements in `data`, `rowtypes`, and `rowheights` do not match.")

    def append(self, content: TableContent):
        """Appends the content of a TableContent.
        Args:
            content (TableContent): content to append.
        Raises:
            Exception: If the number of columns don't match.
        """
        # Note: only the base object's colwidths are retained
        if not len(content.colwidths) == len(self.colwidths):
            raise ValueError("Number of columns does not match")
        self.data.extend(content.data)
        self.rowtypes.extend(content.rowtypes)
        self.rowheights.extend(content.rowheights)
        self.style.extend(content.style)

    def append_empty_row(self, col_span: list[int], rowtype: RowType, parastyle: ParagraphStyle = None) -> TableContent:
        """Adds an empty row to the tablecontent.
        Args:
            content (TableContent): the content to which a row should be added.
            col_span (list[int], optional): Cell range that should be merged. Defaults to [].
            parastyle (ParagraphStyle, optional): Default paragraph style for the cells. Defaults to None.

        Returns:
            TableContent: the modified content.
        """
        rownr = len(self.data)
        tablestyle = TableStyle(
            self.template.metadataTableRAStyle(rownr, rownr)
            if parastyle.alignment in [TA_RIGHT, "RIGHT"]
            else self.template.metadataTableLAStyle(rownr, rownr)
        )
        # Add span information to the style list.
        _, rowheight = NotationTemplate.cell_width_height("quick fox", parastyle=parastyle)
        if col_span[0] != col_span[1]:
            tablestyle.add("SPAN", (col_span[0], len(self.data)), (col_span[1], len(self.data)))
        self.append(
            TableContent(
                data=[[Paragraph("", style=parastyle)] * len(self.colwidths)],
                rowtypes=[rowtype],
                colwidths=self.colwidths,
                rowheights=[rowheight],
                style=tablestyle.getCommands(),
            )
        )
        return self


class NotationTemplate:
    """This class contains all the formatting definitions for the PDF export.
    All text is formatted using Table objects. This facilitates horizontal alignment
    and enables to keep lines together on the same page by disallowing tables to be split."""

    pagesize = A4
    page_width = pagesize[0]
    page_height = pagesize[1]
    left_margin = 0.5 * cm
    right_margin = 0.5 * cm
    top_margin = 0.5 * cm
    bottom_margin = 1 * cm
    body_top_margin = 2.1 * cm
    cell_padding_LR = 0.1 * cm  # Left and right padding
    cell_padding_TB = 0 * cm  # Top and bottom padding (not needed due to `leading` attribute of para styles.)
    table_space_after = 0.5 * cm

    def __init__(self, run_settings: RunSettings):
        self.run_settings = run_settings
        self.title = self.run_settings.notation.title
        self.filepath = self.run_settings.pdf_out_filepath
        self.datestamp = self.run_settings.notation_datetime.strftime(run_settings.pdf_converter.version_fmt).lower()
        self.current_tempo = -1
        self.doc = self._doc_template()
        self.styles = getSampleStyleSheet()
        registerFont(TTFont("Bali Music 5", self.run_settings.configdata.font.ttf_filepath))
        self._init_styles()
        self.notation_row_height = max(
            self.cell_width_height(html.escape("a,a<a="), self.notationStyle)[1],
            self.cell_width_height("quick fox", self.tagStyle)[1],
        )

    @property
    def _body_frame(self) -> Frame:
        """Defines the frame for each page. Each page contains a single frame, apart
           from the header which is written directly to the canvas.
        Returns:
            Frame:
        """
        return Frame(
            self.left_margin,
            self.bottom_margin,
            self.page_width - self.left_margin - self.right_margin,
            self.page_height - self.body_top_margin - self.bottom_margin,
            leftPadding=0,
            bottomPadding=0,
            rightPadding=0,
            topPadding=0,
            id=None,
            showBoundary=0,
        )

    @property
    def _first_page_template(self):
        return PageTemplate(id="First", frames=[self._body_frame], autoNextPageTemplate=1, onPage=self._page_header)

    @property
    def _later_page_template(self):
        return PageTemplate(id="Later", frames=[self._body_frame], autoNextPageTemplate=1, onPage=self._page_header)

    def _init_styles(self):
        """Creates the paragraph and table styles and formats."""
        self.basicparaStyle = ParagraphStyle(
            name="basicparaStyle",
            fontName="Helvetica",
            fontSize=11,
            leading=12,
            textColor=HexColor(0x000000),
            alignment=TA_LEFT,
        )
        self.headerStyleTitle = ParagraphStyle(
            name="headerStyleTitle",
            fontName="Helvetica",
            fontSize=11,
            leading=12,
            textColor=HexColor(0x80340D),
            alignment=TA_LEFT,
        )
        self.headerStylePageNr = ParagraphStyle(
            name="headerStylePageNr",
            fontName="Helvetica",
            fontSize=11,
            leading=12,
            textColor=HexColor(0x000000),
            alignment=TA_CENTER,
        )
        self.headerStyleDateStamp = ParagraphStyle(
            name="headerStyleDateStamp",
            fontName="Helvetica",
            fontSize=9,
            leading=12,
            textColor=HexColor(0x000000),
            alignment=TA_RIGHT,
        )
        self.headerStyleHyperlink = ParagraphStyle(
            name="headerStyleHyperlink",
            fontName="Helvetica",
            fontSize=9,
            leading=11,
            textColor=HexColor(0x000000),
            alignment=TA_RIGHT,
        )
        self.notationStyle = ParagraphStyle(
            name="notationStyle",
            fontName="Bali Music 5",
            fontSize=9,
            leading=11,
            textColor=HexColor(0x000000),
            alignment=TA_LEFT,
            wordWrap=False,
            splitLongWords=False,
        )
        self.tagStyle = ParagraphStyle(
            name="GamelanTag",
            fontName="Helvetica-Bold",
            fontSize=8,
            leading=10,
            textColor=HexColor(0x000000),
            alignment=TA_LEFT,
        )
        self.commentStyle = ParagraphStyle(
            name="GamelanComment",
            fontName="Helvetica",
            fontSize=9,
            leading=11,
            textColor=HexColor(0x808040),
            alignment=TA_LEFT,
        )
        self.metadataSequenceStyle = ParagraphStyle(
            name="GamelanSequence",
            fontName="Helvetica",
            fontSize=9,
            leading=11,
            textColor=HexColor(0x80340D),
            alignment=TA_LEFT,
        )
        self.metadataPartStyle = ParagraphStyle(
            name="GamelanPart",
            fontName="Helvetica-Bold",
            fontSize=11,
            leading=12,
            textColor=HexColor(0x000000),
            alignment=TA_LEFT,
        )
        self.metadataDefaultStyle = ParagraphStyle(
            name="GamelanMetadata",
            fontName="Helvetica-Oblique",
            fontSize=8,
            leading=10,
            textColor=HexColor(0x000000),
            alignment=TA_LEFT,
        )
        self.metadataRepeatStyle = ParagraphStyle(
            name="GamelanMetadataHilite",
            fontName="Helvetica",
            fontSize=9,
            leading=11,
            textColor=colors.blue,
            alignment=TA_RIGHT,
        )
        self.metadataGotoStyle = ParagraphStyle(
            name="GamelanMetadataHilite",
            fontName="Helvetica",
            fontSize=9,
            leading=11,
            textColor=colors.blue,
            alignment=TA_RIGHT,
        )
        self.metadataLabelStyle = ParagraphStyle(
            name="GamelanLabel",
            fontName="Courier-Bold",
            fontSize=9,
            leading=11,
            textColor=colors.blue,
            alignment=TA_LEFT,
        )
        self.metadataLabelCharStyle = '<font color="blue" size="9" face="Courier-Bold">'
        self.gonganIDFontName = "Courier"
        self.gonganIDFontSize = 7
        self.gonganIDFontColor = "black"
        self.gonganIdCharStyle = (
            f'<font color="{self.gonganIDFontColor}" size="{self.gonganIDFontSize}" face="{self.gonganIDFontName}">'
        )

        # metaFormatParameters
        # Parameters for function `ScoreToPDFConverter._append_single_metadata_type` which generates the metadata
        # directives that should appear above and below a gongan. See the function's docstring for more information.
        # cellnr: The table cell in which to write the value. Defaults to 1.
        # col_span, spantype: information about the number of beats (columns) over which to span the text (e.g. in case
        #                      of crescendo). `spantype` specifies the meaning of value `col_span`: either RANGE
        #                      (nr. of cells) or LAST_CELL (cell ID of the last cell of the cell range)
        # parastyle: One of the paragraph styles defined above. Defaults to basicparaStyle.
        # formatter: Function that generates the actual text for the metadata directive. Defaults to default_formatter.
        #            The functions are defined below.
        # before, after: Optional parameters for the `formatter` function.
        self.metaFormatParameters = {
            PartMeta: {
                "col_span": -1,
                "spantype": SpanType.LAST_CELL,
                "parastyle": self.metadataPartStyle,
                "formatter": self._simple_formatter_rml_safe,
            },
            TempoMeta: {
                "cellnr": "first_beat",
                "col_span": "beat_count",
                "spantype": SpanType.RANGE,
                "parastyle": self.metadataDefaultStyle,
                "formatter": self._gradual_change_formatter_rml_safe,
            },
            DynamicsMeta: {
                "cellnr": "first_beat",
                "col_span": "beat_count",
                "spantype": SpanType.RANGE,
                "parastyle": self.metadataDefaultStyle,
                "formatter": self._gradual_change_formatter_rml_safe,
            },
            LabelMeta: {
                "cellnr": "beat",
                # "col_span": -1,
                # "spantype": SpanType.LAST_CELL,
                "parastyle": self.metadataLabelStyle,
                "formatter": self._simple_formatter_rml_safe,
            },
            RepeatMeta: {
                "cellnr": -2,  # right-aligned starting from the last beat. Column -1 is the overflow column.
                "parastyle": self.metadataGotoStyle,
                "before": "repeat ",
                "after": "X",
                "formatter": self._simple_formatter_rml_safe,
            },
            GoToMeta: {
                "cellnr": "from_beat",
                "parastyle": self.metadataGotoStyle,
                "formatter": self._list_formatter_rml_safe,
                "before": "go to ",
            },
            SequenceMeta: {
                "col_span": -1,
                "spantype": SpanType.LAST_CELL,
                "parastyle": self.metadataSequenceStyle,
                "formatter": self._list_formatter_rml_safe,
                "before": "sequence: ",
            },
        }

    # The following functions create table styles for the specified range of rows.

    def notationTableStyle(self, row1: int, row2: int) -> list[tuple]:
        return [
            ("LINEAFTER", (0, row1), (-2, row2), 0.5, colors.black),  # no line after overflow column
            ("FONT", (0, row1), (-1, row2), "Helvetica", 9, 11),
            ("TEXTCOLOR", (0, row1), (-1, row2), colors.black),
            ("ALIGNMENT", (0, row1), (-1, row2), "LEFT"),
            ("LEFTPADDING", (0, row1), (-1, row2), self.cell_padding_LR),
            ("RIGHTPADDING", (0, row1), (-1, row2), self.cell_padding_LR),
            ("BOTTOMPADDING", (0, row1), (-1, row2), 0),
            ("TOPPADDING  ", (0, row1), (-1, row2), 0),
            ("VALIGN", (0, row1), (-1, row2), "MIDDLE"),
        ]

    def notationNoKempliTableStyle(self, row1: int, row2: int) -> list[tuple]:
        return [
            ("LINEAFTER", (0, row1), (-2, row2), 0.5, colors.black, 0, (1, 2)),  # no line after overflow column
            ("FONT", (0, row1), (-1, row2), "Helvetica", 9, 11),
            ("TEXTCOLOR", (0, row1), (-1, row2), colors.black),
            ("ALIGNMENT", (0, row1), (-1, row2), "LEFT"),
            ("LEFTPADDING", (0, row1), (-1, row2), self.cell_padding_LR),
            ("RIGHTPADDING", (0, row1), (-1, row2), self.cell_padding_LR),
            ("BOTTOMPADDING", (0, row1), (-1, row2), 0),
            ("TOPPADDING  ", (0, row1), (-1, row2), 0),
            ("VALIGN", (0, row1), (-1, row2), "MIDDLE"),
        ]

    def metadataTableLAStyle(self, row1: int, row2: int) -> list[tuple]:
        return [
            ("FONT", (0, row1), (-1, row2), "Helvetica", 9, 11),
            ("TEXTCOLOR", (0, row1), (-1, row2), colors.blue),
            ("ALIGNMENT", (0, row1), (-1, row2), "LEFT"),
            ("LEFTPADDING", (0, row1), (-1, row2), self.cell_padding_LR),
            ("RIGHTPADDING", (0, row1), (-1, row2), self.cell_padding_LR),
            ("BOTTOMPADDING", (0, row1), (-1, row2), 0),
            ("TOPPADDING  ", (0, row1), (-1, row2), 0),
            ("VALIGN", (0, row1), (-1, row2), "MIDDLE"),
        ]

    def metadataTableRAStyle(self, row1: int, row2: int) -> list[tuple]:
        return [
            ("FONT", (0, row1), (-1, row2), "Helvetica", 9, 11),
            ("TEXTCOLOR", (0, row1), (-1, row2), colors.blue),
            ("ALIGNMENT", (0, row1), (-1, row2), "RIGHT"),
            ("LEFTPADDING", (0, row1), (-1, row2), self.cell_padding_LR),
            ("RIGHTPADDING", (0, row1), (-1, row2), self.cell_padding_LR),
            ("BOTTOMPADDING", (0, row1), (-1, row2), 0),
            ("TOPPADDING  ", (0, row1), (-1, row2), 0),
            ("VALIGN", (0, row1), (-1, row2), "MIDDLE"),
        ]

    # pylint: enable=missing-function-docstring

    def create_table(self, content: TableContent):
        """Creates a Table object based on the given content"""
        return Table(
            data=content.data,
            colWidths=content.colwidths,
            style=content.style,
            # rowHeights=[self.table_row_height * lines + 2 * self.cell_padding_TB for lines in content.rowheights],
            rowHeights=content.rowheights,
            splitByRow=False,  # dont'split the table over multiple pages
            hAlign="LEFT",  # align table with the left margin
            spaceAfter=self.table_space_after,
        )

    def format_text_rml_safe(self, text: str, charstyle: str):
        """Applies a HTML character format to the text"""
        if charstyle:
            return f"{charstyle}{text}</font>"
        return text

    def _page_header(self, canvas: Canvas, document):
        """Code that should be executed for each new page: it should be assigned to the onPage PageTemplate argument.
        Args:
            canvas (Canvas):
            document (_type_):
        """
        notation_webpage = self.run_settings.pdf_converter.notation_webpage
        headerHeight = 1.5 * cm
        hyperlink_ypos = 1.0 * cm
        lineDistance = 2  # distance between header text bottom and separator line
        lineWidth = 0.5  # width of separator line
        M_width = stringWidth("999", self.headerStylePageNr.fontName, self.headerStylePageNr.fontSize)
        L_R_width = (self.page_width - self.left_margin - self.right_margin - M_width) / 2

        headerY = max(
            self.headerStyleTitle.fontSize, self.headerStylePageNr.fontSize, self.headerStyleDateStamp.fontSize
        )  # maximum height of header text. Used to vertically align text.

        def _write_text(text: str, style: ParagraphStyle, xpos: str, ypos_from_top: int):
            container_width = M_width if xpos == "M" else L_R_width
            p = Paragraph(text, style)
            p.wrap(container_width, headerY)
            Xpos = (
                self.doc.leftMargin
                if xpos.upper() == "L"
                else (
                    (self.pagesize[0] - container_width) / 2
                    if xpos.upper() == "C"
                    else self.pagesize[0] - container_width - self.doc.rightMargin
                )
            )
            p.drawOn(canvas, Xpos, self.pagesize[1] - ypos_from_top - headerY + style.fontSize)

        canvas.saveState()
        _write_text(f"<b>{self.title}</b>", self.headerStyleTitle, "L", headerHeight)
        _write_text(str(document.page), self.headerStylePageNr, "C", headerHeight)
        _write_text(self.datestamp, self.headerStyleDateStamp, "R", headerHeight)
        if document.page == 1:
            _write_text(
                f'notation explained: <link href="{notation_webpage}"><u>{notation_webpage}</u></link>',
                self.headerStyleHyperlink,
                "R",
                hyperlink_ypos,
            )

        canvas.setStrokeColor(HexColor(0x000000))
        canvas.setLineWidth(lineWidth)
        canvas.line(
            self.doc.leftMargin,
            self.pagesize[1] - headerHeight - lineDistance,
            self.pagesize[0] - self.doc.rightMargin,
            self.pagesize[1] - headerHeight - lineDistance,
        )
        canvas.restoreState()

    def _doc_template(self) -> SimpleDocTemplate:
        template = SimpleDocTemplate(
            filename=self.filepath,
            pagesize=self.pagesize,
            showBoundary=0,
            leftMargin=self.left_margin,
            rightMargin=self.right_margin,
            topMargin=self.top_margin,
            bottomMargin=self.bottom_margin,
            allowSplitting=1,
            title=self.title,
            author="BaliMusic",
            _pageBreakQuick=1,
            encrypt=None,
        )
        template.pageTemplates = [self._first_page_template, self._later_page_template]
        return template

    @classmethod
    def _simple_formatter_rml_safe(
        cls,
        meta: MetaData,
        before: str = "",
        after: str = "",
    ) -> str:
        """Simple formatter for metadata. Adds the value to the given paragraph.
        Args:
            value (Any): Value that should be written. If missing, the metadata DEFAULTPARAM attribute will be used.
            meta (MetaData): Metadata object.
            before (str, optional): Text that should precede the value. Defaults to "".
            after (str, optional): Text that should follow the value. Defaults to "".
            paragraph (Paragraph, optional): The paragraph to which the value should be written. Defaults to None.
            charstyle (CharacterStyle, optional): Character style for the added text. Defaults to `metadatastyle`.
        """
        value = getattr(meta, meta.DEFAULTPARAM)
        return html.escape(f"{before}{value}{after}")

    def _list_formatter_rml_safe(
        self,
        meta: MetaData,
        before: str = "",
        after: str = "",
    ) -> str:
        """Formatter for a metadata list value. Formats the value to a comma separated list.
            The list items are formatted using the `labelstyle` character style.
        Args:
            value (typing.Any): Value that should be written. If missing, the metadata DEFAULTPARAM attribute will
                                be used.
            meta (MetaData): Metadata object.
            before (str, optional): Text that should precede the value. Defaults to "".
            after (str, optional): Text that should follow the value. Defaults to "".
            paragraph (Paragraph, optional): The paragraph to which the value should be written. Defaults to None.
            charstyle (CharacterStyle, optional): Character style for the added text. Defaults to `metadatastyle`.
        """
        value = getattr(meta, meta.DEFAULTPARAM)
        value_ = ", ".join(value) if isinstance(value, list) else value
        value_ = self.format_text_rml_safe(value_, self.metadataLabelCharStyle)
        return f"{html.escape(before)}{value_}{html.escape(after)}"

    def _gradual_change_formatter_rml_safe(self, meta: MetaData) -> str:
        """Formatter for GradualChangeMetadata subclasses. These values can include a range of beats to which the
           metadata applies. Called for TEMPO and DYNAMICS metadata which can gradually change over several beats.
           The value will be preceded or followed by a dotted line that will reach to the right margine of the
           (merged) cell.
        Args:
            value (typing.Any): Value that should be written. If missing, the metadata DEFAULTPARAM attribute will
                                be used.
            meta (MetaData): Metadata object.
            before (str, optional): Text that should precede the value. Defaults to "".
            after (str, optional): Text that should follow the value. Defaults to "".
            paragraph (Paragraph, optional): The paragraph to which the value should be written. Defaults to None.
            charstyle (CharacterStyle, optional): Character style for the added text. Defaults to `metadatastyle`.
        """
        # If the metadata spans several beats, dots will be added over the width of the corresponding columns.
        value = getattr(meta, meta.DEFAULTPARAM)
        value_ = None

        if meta.metatype == "TEMPO":
            if self.current_tempo == -1:
                self.current_tempo = value
                # Suppress initial tempo
                return None
            if value == self.current_tempo:
                # No tempo change
                return None
            value_ = ("faster" if value > self.current_tempo else "slower") + "{dots}"
            self.current_tempo = value

        elif meta.metatype == "DYNAMICS":
            position_tags = to_aggregated_tags(meta.positions)
            value_ = f"{", ".join(position_tags)}{": " if position_tags else ""}{"{dots}"}{value}"
        return html.escape(value_)

    @classmethod
    def cell_width_height(cls, rml_safe_text: str, parastyle: ParagraphStyle, width: int = 10e6) -> tuple[int]:
        """Calculates the required cell dimensions for the given text and available width (in pt).
        The function takes text wrapping and cell padding into account and returns the actual width and height
        of the text.
        The default value for `width` will return the actual text width + cell padding (10e6 pt > 138.000 inches).
        Args:
            rml_safe_text (str): the text to evaluate. The text should be rml safe (formatted with html.escape).
            parastyle (ParagraphStyle): style to apply to the text.
            width (int, optional): available width. Defaults to 10e6.
        Returns:
            tuple[int]: _description_
        """
        if rml_safe_text == "":
            return 0, 0
        height = 10e6
        avail_width = width - 2 * cls.cell_padding_LR
        para = Paragraph(rml_safe_text, parastyle)
        act_h = para.wrap(avail_width, height)[1] + 2 * cls.cell_padding_TB
        act_w = max(para.getActualLineWidths0()) + 2 * cls.cell_padding_LR
        return (act_w, act_h)
