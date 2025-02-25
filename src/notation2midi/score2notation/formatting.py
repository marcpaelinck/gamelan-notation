import os
from dataclasses import dataclass, field
from datetime import datetime

from more_itertools import flatten
from reportlab.lib import colors, utils
from reportlab.lib.colors import HexColor
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.pdfbase.pdfmetrics import registerFont, stringWidth
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen.canvas import Canvas
from reportlab.platypus import (
    Flowable,
    Frame,
    FrameBreak,
    PageBegin,
    PageBreak,
    PageTemplate,
    Paragraph,
    SimpleDocTemplate,
)
from reportlab.platypus.doctemplate import _doNothing

from src.settings.classes import RunSettings


class NotationTemplate:

    pagesize = A4
    page_width = pagesize[0]
    page_height = pagesize[1]
    left_margin = 0.5 * cm
    right_margin = 0.5 * cm
    top_margin = 0.5 * cm
    bottom_margin = 1 * cm
    body_top_margin = 2.1 * cm
    cell_padding = 0.1 * cm  # Left and right padding

    def __init__(self, run_settings: RunSettings):
        self.run_settings = run_settings
        self.title = self.run_settings.notation.title
        fpath, ext = os.path.splitext(self.run_settings.notation.midi_out_filepath)
        self.filepath = fpath + "_ALT.pdf"
        last_modif_epoch = os.path.getmtime(self.run_settings.notation.notation_filepath)
        self.datestamp = datetime.fromtimestamp(last_modif_epoch).strftime("%d-%b-%Y")
        self.doc = self._doc_template()
        self.styles = getSampleStyleSheet()
        registerFont(TTFont("Bali Music 5", self.run_settings.font.ttf_filepath))
        self._init_styles()

    @property
    def _body_frame(self) -> Frame:
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

    def notationTableStyle(self, row1: int, row2: int) -> list[tuple]:
        return [
            ("LINEAFTER", (0, row1), (-2, row2), 0.5, colors.black),  # no line after overflow column
            ("FONT", (0, row1), (-1, row2), "Helvetica", 9, 11),
            ("TEXTCOLOR", (0, row1), (-1, row2), colors.black),
            ("ALIGNMENT", (0, row1), (-1, row2), "LEFT"),
            ("LEFTPADDING", (0, row1), (-1, row2), self.cell_padding),
            ("RIGHTPADDING", (0, row1), (-1, row2), self.cell_padding),
            ("BOTTOMPADDING", (0, row1), (-1, row2), 0),
            ("TOPPADDING  ", (0, row1), (-1, row2), 0),
            ("VALIGN", (0, row1), (-1, row2), "MIDDLE"),
        ]

    def metadataTableLAStyle(self, row1: int, row2: int) -> list[tuple]:
        return [
            ("FONT", (0, row1), (-1, row2), "Helvetica", 9, 11),
            ("TEXTCOLOR", (0, row1), (-1, row2), colors.blue),
            ("ALIGNMENT", (0, row1), (-1, row2), "LEFT"),
            ("LEFTPADDING", (0, row1), (-1, row2), self.cell_padding),
            ("RIGHTPADDING", (0, row1), (-1, row2), self.cell_padding),
            ("BOTTOMPADDING", (0, row1), (-1, row2), 0),
            ("TOPPADDING  ", (0, row1), (-1, row2), 0),
            ("VALIGN", (0, row1), (-1, row2), "MIDDLE"),
        ]

    def metadataTableRAStyle(self, row1: int, row2: int) -> list[tuple]:
        return [
            ("FONT", (0, row1), (-1, row2), "Helvetica", 9, 11),
            ("TEXTCOLOR", (0, row1), (-1, row2), colors.blue),
            ("ALIGNMENT", (0, row1), (-1, row2), "RIGHT"),
            ("LEFTPADDING", (0, row1), (-1, row2), self.cell_padding),
            ("RIGHTPADDING", (0, row1), (-1, row2), self.cell_padding),
            ("BOTTOMPADDING", (0, row1), (-1, row2), 0),
            ("TOPPADDING  ", (0, row1), (-1, row2), 0),
            ("VALIGN", (0, row1), (-1, row2), "MIDDLE"),
        ]

    def format_text(self, text: str, charstyle: str):
        if charstyle:
            return f"{charstyle}{text}</font>"
        return text

    def _page_header(self, canvas: Canvas, document):
        """Code that should be executed for each new page: it can be assigned to the onPage PageTemplate argument.
        Args:
            canvas (Canvas):
            document (_type_):
        """
        headerHeight = 1.5 * cm
        lineDistance = 2  # distance between header text bottom and separator line
        lineWidth = 0.5  # width of separator line
        M_width = stringWidth("999", self.headerStylePageNr.fontName, self.headerStylePageNr.fontSize)
        L_R_width = (self.page_width - self.left_margin - self.right_margin - M_width) / 2

        headerY = max(
            self.headerStyleTitle.fontSize, self.headerStylePageNr.fontSize, self.headerStyleDateStamp.fontSize
        )  # maximum height of header text. Used to vertically align text.

        def _write_text(text: str, style: ParagraphStyle, position: str = "L"):
            container_width = M_width if position == "M" else L_R_width
            p = Paragraph(text, style)
            p.wrap(container_width, headerY)
            Xpos = (
                self.doc.leftMargin
                if position.upper() == "L"
                else (
                    (self.pagesize[0] - container_width) / 2
                    if position.upper() == "C"
                    else self.pagesize[0] - container_width - self.doc.rightMargin
                )
            )
            p.drawOn(canvas, Xpos, self.pagesize[1] - headerHeight - headerY + style.fontSize)

        canvas.saveState()
        _write_text(f"<b>{self.title}</b>", self.headerStyleTitle, "L")
        _write_text(str(document.page), self.headerStylePageNr, "C")
        _write_text(self.datestamp, self.headerStyleDateStamp, "R")
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
