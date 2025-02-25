import itertools
import os
import pickle
import typing
from dataclasses import dataclass, field
from enum import Enum
from os import path
from typing import Self

from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import cm
from reportlab.pdfbase.pdfmetrics import registerFont, stringWidth
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import Paragraph, Table, TableStyle

from src.common.classes import Gongan, Note, Score
from src.common.constants import InstrumentType, Position
from src.common.metadata_classes import MetaDataBaseModel
from src.notation2midi.classes import ParserModel
from src.notation2midi.score2notation.formatting import NotationTemplate
from src.notation2midi.score2notation.score_to_notation import aggregate_positions
from src.notation2midi.score2notation.utils import (
    clean_staves,
    measure_to_str,
    stringWidth_fromNotes,
)


class SpanType(Enum):
    RANGE = 1
    LAST_CELL = 2


@dataclass
class TableContent:

    data: list[list[str | Paragraph]] = field(default_factory=list)
    style: list[tuple] = field(default_factory=list)
    colwidths: list[float] = field(default_factory=list)

    def append(self, table: Self):
        # Note: only the base object's colwidths are retained
        if not (len(table.colwidths) == len(self.colwidths)):
            raise Exception("Number of columns does not match")
        self.data.extend(table.data)
        self.style.extend(table.style)


class ScoreToPDFConverter(ParserModel):
    TAG_COLWIDTH = 2.3 * cm
    basicparastyle = None
    metadatastyle = None
    W = 0
    H = 1

    def __init__(self, score: Score, pickle: bool = True):
        super().__init__(self.ParserType.SCORETOPDF, score.settings)
        self.pdf_settings = self.run_settings.pdf_converter
        fpath, ext = os.path.splitext(score.settings.notation.midi_out_filepath)
        self.filepath = fpath + "_ALT.pdf"
        # self.canvas: Canvas = Canvas(self.filepath, pagesize=A4)
        self.score = score
        self.template = NotationTemplate(self.score.settings)
        self.pickle = pickle
        self.current_tempo = -1
        self.current_dynamics = -1
        registerFont(TTFont("Bali Music 5", self.run_settings.font.ttf_filepath))
        self.story = []

    def _to_aggregated_tags(self, positions: list[Position]) -> list[str]:
        tags = set(pos.instrumenttype.lower() for pos in positions)
        gangsa = {InstrumentType.PEMADE.lower(), InstrumentType.KANTILAN.lower()}
        if gangsa.issubset(tags):
            tags = tags.difference(gangsa).union({"gangsa"})
        return tags

    def _append_empty_row(
        self, table: TableContent, colwidths: int, col_span: list[int] = [], parastyle: ParagraphStyle = None
    ) -> TableContent:
        rownr = len(table.data)
        tablestyle = TableStyle(
            self.template.metadataTableRAStyle(rownr, rownr)
            if parastyle.alignment in [TA_RIGHT, "RIGHT"]
            else self.template.metadataTableLAStyle(rownr, rownr)
        )
        if col_span[0] != col_span[1]:
            tablestyle.add("SPAN", (col_span[0], len(table.data)), (col_span[1], len(table.data)))
        table.data.append([Paragraph("", style=parastyle)] * len(colwidths))
        table.style.extend(tablestyle.getCommands())
        return table

    def _default_formatter(
        self,
        value: typing.Any | None,
        meta: MetaDataBaseModel,
        before: str = "",
        after: str = "",
    ) -> str:
        """Simple formatter for metadata. Adds the value to the given paragraph.
        Args:
            value (typing.Any): Value that should be written. If missing, the metadata DEFAULTPARAM attribute will be used.
            meta (MetaDataBaseModel): Metadata object.
            before (str, optional): Text that should precede the value. Defaults to "".
            after (str, optional): Text that should follow the value. Defaults to "".
            paragraph (Paragraph, optional): The paragraph to which the value should be written. Defaults to None.
            charstyle (CharacterStyle, optional): Character style for the added text. Defaults to `metadatastyle`.
        """
        value_ = value or getattr(meta, meta.DEFAULTPARAM)
        return f"{before}{value_}{after}"

    def _list_formatter(
        self,
        value: list[str],
        meta: MetaDataBaseModel,
        before: str = "",
        after: str = "",
    ) -> str:
        """Formatter for a metadata list value. Formats the value to a comma separated list.
            The list items are formatted using the `labelstyle` character style.
        Args:
            value (typing.Any): Value that should be written. If missing, the metadata DEFAULTPARAM attribute will be used.
            meta (MetaDataBaseModel): Metadata object.
            before (str, optional): Text that should precede the value. Defaults to "".
            after (str, optional): Text that should follow the value. Defaults to "".
            paragraph (Paragraph, optional): The paragraph to which the value should be written. Defaults to None.
            charstyle (CharacterStyle, optional): Character style for the added text. Defaults to `metadatastyle`.
        """
        value_ = value or getattr(meta, meta.DEFAULTPARAM)
        if isinstance(value_, list):
            value_ = ", ".join(value_)
        value_ = self.template.format_text(value_, self.template.metadataLabelCharStyle)
        return f"{before}{value_}{after}"

    def _gradual_change_formatter(
        self,
        value: list[str],
        meta: MetaDataBaseModel,
        before: str = "",
        after: str = "",
    ) -> str:
        """Formatter for GradualChangeMetadata subclasses. These values can include a range of beats to which the metadata
           applies. Called for TEMPO and DYNAMICS metadata which can gradually change over several beats.
           The value will be preceded or followed by a dotted line that will reach to the right margine of the (merged) cell.
        Args:
            value (typing.Any): Value that should be written. If missing, the metadata DEFAULTPARAM attribute will be used.
            meta (MetaDataBaseModel): Metadata object.
            before (str, optional): Text that should precede the value. Defaults to "".
            after (str, optional): Text that should follow the value. Defaults to "".
            paragraph (Paragraph, optional): The paragraph to which the value should be written. Defaults to None.
            charstyle (CharacterStyle, optional): Character style for the added text. Defaults to `metadatastyle`.
        """
        # If the metadata spans several beats, a tab character will be added before or after the value and a tab stop
        # with preceding dashes will be added at the right-hand margin of the merged cell.
        if meta.metatype == "TEMPO":
            if self.current_tempo == -1:
                self.current_tempo = meta.value
                return None
            value = "faster{dots}" if meta.value > self.current_tempo else "slower{dots}"
            self.current_tempo = meta.value
        elif meta.metatype == "DYNAMICS":
            position_tags = self._to_aggregated_tags(meta.positions)
            value = f"{", ".join(position_tags)}{": " if position_tags else ""}{"{dots}"}{meta.abbreviation}"
            self.current_dynamics = meta.value
        return value

    def _append_single_metadata_type(
        self,
        table: TableContent,
        metalist: list[MetaDataBaseModel],
        value: str = None,
        cellnr: int | str = 1,
        spantype: SpanType = SpanType.LAST_CELL,
        col_span: int | str | None = None,
        parastyle: ParagraphStyle = None,
        before: str = "",
        after: str = "",
        formatter: typing.Callable = None,
    ) -> TableContent:
        """Generic method that adds metadata items of the same type. A row is added to the table content for each metadata item.
           Note that table contains an overflow column (after the last beat column) to accommodate long metadata texts.
        Args:
            table (Table): The table to which to add the metadata.
            metalist (list[MetaData]): List of similar metadata items.
            value (str, optional): The value to print. Defaults to the default attrribute of the metadata item (set in DEFAULTPARAM).
            cellnr: (int, optional): The table cell in which to write the value. Defaults to 1.
            spantype (SpanType): LAST_CELL: Text should span from columns cellnr through col_span. RANGE: col_span Text should span over col_span columns.
            col_span (int | str, optional): Value for the text span, either a column id or a metadata attribute name. Defaults to None.
            parastyle (ParagraphStyle, optional): Paragraph style. Defaults to basicparastyle.
            before (str, optional): Text to print before the value. Defaults to "".
            after (str, optional): Text to print after the value. Defaults to "".
            formatter (Callable, optional): Function that generates and formats the text. Defaults to default_formatter.
        Returns:
            TableContent:
        """
        colwidths = table.colwidths
        cellspans = []
        first_row = len(table.data)

        def span_width(col1: int, col2: int):
            return sum(colwidths[c] for c in range(col1, col2 + 1))

        def overlap(a: tuple[int], b: tuple[int]):
            # Span format is ('SPAN', (sc,sr), (ec,er))
            # We expect all the spans to combine cells on the same row.
            return not max(0, min(a[2][0], b[2][0]) - max(a[1][0], b[1][0]))

        cell_alignment = "RIGHT" if parastyle.alignment in [TA_RIGHT, "RIGHT"] else "LEFT"
        for meta in metalist:
            parastyle = parastyle or self.template.basicparaStyle
            cellnr_ = getattr(meta, cellnr) if isinstance(cellnr, str) else cellnr
            cellnr_ = len(colwidths) - 1 if cellnr_ < 0 else cellnr_
            if col_span:
                span = getattr(meta, col_span) if isinstance(col_span, str) else col_span
                if spantype is SpanType.RANGE:
                    lastcellnr = len(colwidths) - 1 if span == -1 else cellnr_ if span == 0 else cellnr_ + span - 1
                    col_range = (cellnr_, lastcellnr)
                elif spantype is SpanType.LAST_CELL:
                    span = len(colwidths) - 1 if span < 0 else 1 if span == 0 else span
                    col_range = (cellnr_, cellnr_ + span - 1)
                else:
                    raise ValueError(f"Unexpected value {spantype} for argument spantype.")
            else:
                col_range = (cellnr_, cellnr_)

            formatter = formatter or self._default_formatter
            value = formatter(value, meta, before=before, after=after)
            if not value:
                continue
            if "passes" in meta.model_fields:
                if meta.passes:
                    if any(p for p in meta.passes if p > 0):
                        value += f" (pass {','.join(str(p) for p in meta.passes)})"
            # merge additional cells if necessary to accommondate the text width
            textwidth = stringWidth(value.format(dots=""), parastyle.fontName, parastyle.fontSize)
            delta = 0.2 * cm
            span_range = col_range
            if span_width(*col_range) < textwidth + delta:
                # if text is in the last gongan column: merge the cell with the overflow cell to the right
                # Merge the cell with empty adjacent cells if possible until the required width is reached.
                step = -1 if cell_alignment == "RIGHT" else 1
                adjacent_cell = span_range[0] if cell_alignment == "RIGHT" else span_range[1]
                while sum(
                    colwidths[c] for c in range(min(adjacent_cell, cellnr_), max(adjacent_cell, cellnr_) + 1)
                ) < textwidth + delta and 0 <= adjacent_cell + step < len(colwidths):
                    adjacent_cell += step
                    # TODO: if the adjcell is the rightmost cell of the table, adjust the column width if needed
                if adjacent_cell != cellnr_:
                    span_range = min(adjacent_cell, cellnr_), max(adjacent_cell, cellnr_)
                    cellnr_ = min(adjacent_cell, cellnr_)

            span = None
            if span_range[0] != span_range[1]:
                span = ("SPAN", (span_range[0], len(table.data)), (span_range[1], len(table.data)))

            # Add dots if necessary for metadata spanning more than one column
            if col_range[0] != col_range[1]:
                freespace = span_width(*col_range) - textwidth - delta
                if freespace > 0:
                    nrdots = int(freespace / stringWidth("." * 10, parastyle.fontName, parastyle.fontSize) * 10)
                    dots = "." * nrdots
                else:
                    dots = ""
            else:
                dots = ""
            value = Paragraph(value.format(dots=dots), parastyle)
            row = [value if i == cellnr_ else "" for i in range(len(colwidths))]

            # Check if the content can be added to the previous row
            if table.data:
                prevrow_spans = [cmd for cmd in table.style if cmd[0] == "SPAN" and cmd[1][1] == len(table.data) - 1]
                content_overlap = any(cell1 and cell2 for cell1, cell2 in zip(row, table.data[-1]))
                span_overlap = span and any(overlap(s1, s2) for s1, s2 in itertools.product([span], prevrow_spans))
                if not content_overlap and not span_overlap:
                    row = [c1 or c2 for c1, c2 in zip(table.data.pop(), row)]
                    if span:
                        span_tolist = list(span)
                        span_tolist[1:] = [(el[0], el[1] - 1) for el in span[1:]]
                        span = tuple(span_tolist)
            if span:
                cellspans.append(span)
            table.data.append(row)

        # Update the table style list
        last_row = len(table.data) - 1
        style_cmds = (
            self.template.metadataTableRAStyle(first_row, last_row)
            if cell_alignment == "RIGHT"
            else self.template.metadataTableLAStyle(first_row, last_row)
        ) + cellspans
        tablestyle = TableStyle(style_cmds)
        table.style.extend(tablestyle.getCommands())

        return table

    def _append_comments(self, table: TableContent, comments: list[str]) -> TableContent:
        for comment in comments:
            if not comment.startswith("#"):
                table = self._append_empty_row(
                    table, colwidths=table.colwidths, col_span=[1, -1], parastyle=self.template.basicparaStyle
                )
                table.data[-1][1] = Paragraph(text=f"{comment}", style=self.template.commentStyle)
                table.style.append(("SPAN", (1, len(table.data)), (len(table.colwidths) - 1, len(table.data))))
        return table

    def _append_metadata(self, table: TableContent, gongan: Gongan, above_notation: bool) -> TableContent:
        """Adds the gongan metadata and comments that should appear above or below the notation part.
        Only processes the metadata that is meaningful for the PDF notation. E.g. ValidationMeta,
        GonganMeta, AutoKempyungMeta, OctavateMeta are skipped.
        Args:
            table (TableContent): content to which the new rows should be added
            gongan (Gongan): the gongan to which the metadata belongs
            above_notation (bool): Selects which metadata to generate
        """
        metatypes = {meta.data.metatype for meta in gongan.metadata}
        metadict = {
            metatype: [meta.data for meta in gongan.metadata if meta.data.metatype == metatype]
            for metatype in metatypes
        }
        if above_notation:
            # Content that should occur before the notation part of the gongan
            # still to add DynamicsMeta, KempliMeta, SuppressMeta, TempoMeta
            if metalist := metadict.get("PART", None):
                table = self._append_single_metadata_type(
                    table, metalist=metalist, col_span=-1, parastyle=self.template.metadataPartStyle
                )

            table = self._append_comments(table, gongan.comments)

            if metalist := metadict.get("LABEL", None):
                table = self._append_single_metadata_type(
                    table,
                    metalist=metalist,
                    cellnr="beat",
                    col_span=-1,
                    parastyle=self.template.metadataLabelStyle,
                )

            if metalist := metadict.get("TEMPO", None):
                table = self._append_single_metadata_type(
                    table,
                    metalist=metalist,
                    cellnr="first_beat",
                    col_span="beat_count",
                    spantype=SpanType.RANGE,
                    parastyle=self.template.metadataDefaultStyle,
                    formatter=self._gradual_change_formatter,
                )

            if metalist := metadict.get("DYNAMICS", None):
                table = self._append_single_metadata_type(
                    table,
                    metalist=metalist,
                    cellnr="first_beat",
                    col_span="beat_count",
                    spantype=SpanType.RANGE,
                    parastyle=self.template.metadataDefaultStyle,
                    formatter=self._gradual_change_formatter,
                )

        if not above_notation:
            # Content that should occur after the notation part of the gongan
            if metalist := metadict.get("REPEAT", None):
                table = self._append_single_metadata_type(
                    table,
                    metalist,
                    col_span=len(gongan.beats),  # right-aligned: do not use extra column
                    before="repeat ",
                    after="X",
                    parastyle=self.template.metadataGotoStyle,
                )

            if metalist := metadict.get("GOTO", None):
                table = self._append_single_metadata_type(
                    table,
                    metalist,
                    cellnr="from_beat",
                    before="go to ",
                    parastyle=self.template.metadataGotoStyle,
                    formatter=self._list_formatter,
                )

            if metalist := metadict.get("SEQUENCE", None):
                table = self._append_empty_row(
                    table, colwidths=table.colwidths, col_span=[1, -1], parastyle=self.template.basicparaStyle
                )  # add an empty row as a separator
                table = self._append_single_metadata_type(
                    table,
                    metalist,
                    col_span=-1,
                    before="sequence: ",
                    parastyle=self.template.metadataSequenceStyle,
                    formatter=self._list_formatter,
                )
        return table

    def _staves_to_tabledata(
        self, staves: dict[Position, list[list[Note]]], pos_tags: dict[Position, str]
    ) -> tuple[list[list[typing.Any]], list[float]]:
        colwidths = []
        data = list()
        for position in sorted(list(pos_tags.keys()), key=lambda x: x.sequence):
            if not colwidths:
                colwidths = [0] * len(staves[position])
            row = [Paragraph(pos_tags[position], self.template.tagStyle)]
            data.append(row)
            for colnr, measure in enumerate(staves[position]):
                text = measure_to_str(measure)
                para = Paragraph(text, self.template.notationStyle)
                # stringWidth does not take negative
                w = stringWidth_fromNotes(
                    measure, self.template.notationStyle.fontName, self.template.notationStyle.fontSize
                )
                colwidths[colnr] = max(colwidths[colnr], w + 0.2 * cm)
                row.append(para)
        return data, colwidths

    def _convert_to_pdf(self) -> None:  # score_validation
        """Converts a score object to readable notation and saves it to PDF format (via DOCX).
        Args:
            score (Score): The score
        """
        METADATA_KEEP = ["DYNAMICS", "GOTO", "LABEL", "PART", "REPEAT", "SEQUENCE", "SUPPRESS", "TEMPO"]
        for gongan in self.score.gongans:
            if not gongan.beats:
                continue
            staves_ = clean_staves(gongan)
            pos_tags = aggregate_positions(gongan)
            notation_data, beat_colwidths = self._staves_to_tabledata(staves_, pos_tags)
            last_col_width = max(
                self.template.doc.pageTemplate.frames[0].width - sum(beat_colwidths) - self.TAG_COLWIDTH, 0
            )
            colwidths = [self.TAG_COLWIDTH] + beat_colwidths + [last_col_width]

            # Create an empty content container
            content: TableContent = TableContent(data=[], colwidths=colwidths, style=[])
            content = self._append_metadata(content, gongan=gongan, above_notation=True)
            row1, row2 = len(content.data), len(content.data) + len(notation_data) - 1
            content.append(
                TableContent(
                    data=notation_data,
                    colwidths=colwidths,
                    style=self.template.notationTableStyle(row1, row2),
                )
            )
            content = self._append_metadata(content, gongan, above_notation=False)
            gongan_table = Table(
                data=content.data,
                colWidths=colwidths,
                style=content.style,
                rowHeights=0.4 * cm,
                splitByRow=False,
                hAlign="LEFT",
                spaceAfter=0.5 * cm,
            )
            self.story.append(gongan_table)
        self.template.doc.build(self.story)

    def is_docfile_closed():
        return

    @ParserModel.main
    def create_notation(self):
        if self.pickle:
            with open(self.filepath.replace("docx", "pickle"), "wb") as picklefile:
                pickle.dump(self.score, picklefile)

        self._convert_to_pdf()
        self.logger.info(f"Notation file saved as {self.filepath}")


if __name__ == "__main__":
    # print(ScoreToPDFConverter._bali_music_5_width(40) / 1 * cm)
    # print(textwidth("This is a very long sentence, try this!", font="Arial", fontsize=10).cm)
    # exit()

    class Source(Enum):
        SINOMLADRANG = {
            "folder": r"C:\Users\marcp\Documents\administratie\_VRIJETIJD_REIZEN\Scripts-Programmas\PythonProjects\gamelan-notation\data\notation\sinom ladrang",
            "filename": "Sinom Ladrang_full_GAMELAN1.pickle",
        }
        LEGONGMAHAWIDYA = {
            "folder": r"C:\Users\marcp\Documents\administratie\_VRIJETIJD_REIZEN\Scripts-Programmas\PythonProjects\gamelan-notation\data\notation\legong mahawidya",
            "filename": "Legong Mahawidya_full_GAMELAN1.pickle",
        }
        SEKARGENDOT = {
            "folder": r"C:\Users\marcp\Documents\administratie\_VRIJETIJD_REIZEN\Scripts-Programmas\PythonProjects\gamelan-notation\data\notation\sekar gendot",
            "filename": "Sekar Gendot_full_GAMELAN1.pickle",
        }
        LENGKER = {
            "folder": r"C:\Users\marcp\Documents\administratie\_VRIJETIJD_REIZEN\Scripts-Programmas\PythonProjects\gamelan-notation\data\notation\lengker",
            "filename": "Lengker_full_GAMELAN1.pickle",
        }

    source = Source.LEGONGMAHAWIDYA

    path = os.path.join(source.value["folder"], source.value["filename"])
    with open(path, "rb") as picklefile:
        score = pickle.load(picklefile)
        ScoreToPDFConverter(score, False)._convert_to_pdf()
