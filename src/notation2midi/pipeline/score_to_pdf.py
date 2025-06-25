"""Generates a PDF notation document based on a Score object."""

from __future__ import annotations

import html
import itertools
import math
from typing import Callable, override

from reportlab.lib.enums import TA_RIGHT
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import cm
from reportlab.pdfbase.pdfmetrics import registerFont, stringWidth
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import Paragraph, TableStyle

from src.common.classes import Gongan
from src.common.constants import Modifier, Position
from src.common.notes import Note
from src.notation2midi.classes import Agent
from src.notation2midi.execution.execution import Score
from src.notation2midi.metadata_classes import (
    DynamicsMeta,
    GoToMeta,
    LabelMeta,
    LoopMeta,
    MetaData,
    PartMeta,
    SequenceMeta,
    TempoMeta,
)
from src.notation2midi.pipeline.parse_notation import PassID
from src.notation2midi.score2notationutils.formatting import (
    NotationTemplate,
    RowType,
    SpanType,
    TableContent,
)
from src.notation2midi.score2notationutils.utils import (
    aggregate_positions,
    clean_staves,
    has_kempli_beat,
    measure_to_str_rml_safe,
)
from src.settings.classes import RunSettings
from src.settings.constants import FontFields


class PDFGeneratorAgent(Agent):
    """PDF generator"""

    LOGGING_MESSAGE = "EXPORTING PDF NOTATION"
    EXPECTED_INPUT_TYPES = (Agent.InputOutputType.RUNSETTINGS, Agent.InputOutputType.UNBOUNDSCORE)
    RETURN_TYPE = Agent.InputOutputType.PDFFILE

    TAG_COLWIDTH = 2.3 * cm
    basicparastyle = None
    metadatastyle = None
    W = 0
    H = 1

    def __init__(self, run_settings: RunSettings, score: Score):
        super().__init__(run_settings)
        self.score = score
        self.template = NotationTemplate(self.score.settings)
        self.current_tempo = -1
        self.current_dynamics = -1  # Not used currently
        registerFont(TTFont("Bali Music 5", self.run_settings.configdata.font.ttf_filepath))
        self.story = []
        self.omit_octave_diacritics = run_settings.pdf_converter.omit_octave_diacritics
        self.octave_diacritics = [
            rec[FontFields.SYMBOL]
            for rec in run_settings.data.font
            if rec[FontFields.MODIFIER] in [Modifier.OCTAVE_0, Modifier.OCTAVE_2]
        ]

    @override
    @classmethod
    def run_condition_satisfied(cls, run_settings: RunSettings):
        return (
            run_settings.options.notation_to_midi.save_pdf_notation
            and run_settings.part_id == run_settings.notationfile.generate_pdf_part_id
        )

    def _append_single_metadata_type(
        self,
        content: TableContent,
        metalist: list[MetaData],
        cellnr: int | str = 1,
        spantype: SpanType = SpanType.LAST_CELL,
        col_span: int | str | None = None,
        parastyle: ParagraphStyle = None,
        formatter: Callable = None,
        **kwargs,
    ) -> TableContent:
        """Generic method that adds metadata items with the same metatype. A row is added to the table content for each
           metadata item. The `content` contains an overflow column (after the last beat column) to accommodate long
           metadata texts.

           Metadata directives are added as additional rows to the table containing the notation instead of putting
           them in separate 'Paragraph' containers. This enables to align the directives with specific columns/beats,
           and it makes it possible to keep the entire gongan on the same page. The latter is achieved by setting the
           value of parameter splitByRow of reportlab.platypus.Table to False.
           The parameters `cellnr`, `col_span` and `spantype` contain information about the alignment of the text.
           `cellnr` and `col_span` contain either numeric or string values. A string value indicate that the value of
           the corresponding attribute of the metadata object should be used.
           The number of columns is equal to the number of beats + 2. The first column contains the position names, the
           last one is an overflow column which extends to the right page margin. Parameters `col_span` and `spantype`
           contain information about the number of beats (columns) over which to span the text (e.g. in case of
           crescendo).
           Value -1 for `col_span` in combination with `spantype` LAST_CELL indicates that the text can extend to the
           end of the line.

           If the text width is larger than the width of the assigned cell or cell range, the method will expand the
           range as much as possible to make te text fit on one line.
        Args:
            content (TableContent): The table content to which to add the metadata.
            metalist (list[MetaData]): List of similar metadata items.
            cellnr: (int, optional): The table cell in which to write the value, also first cell of the cell range.
                                     Defaults to 1.
            spantype (SpanType): value LAST_CELL - `col_span` contains the id of the last cell of the cell range.
                                 value RANGE - `col_span` contains the number of cells for the cell range.
            col_span (int | str, optional): Value for the cell range, either a column id or a metadata attribute name.
                                            Defaults to None.
            parastyle (ParagraphStyle, optional): Paragraph style. Defaults to basicparastyle.
            before (str, optional): Text to print before the value. Defaults to "".
            after (str, optional): Text to print after the value. Defaults to "".
            formatter (Callable, optional): Function that generates and formats the text. Defaults to default_formatter.
        Returns:
            TableContent:
        """

        colwidths = content.colwidths[:-1]  # Available columns excluding the overflow column
        all_colwidths = content.colwidths
        cellspans = []
        first_row = len(content.data)

        def span_width(col1: int, col2: int):
            return sum(content.colwidths[c] for c in range(col1, col2 + 1))

        def span_overlap(a: tuple[int], b: tuple[int]):
            """Determines if two 'SPAN' TableStyle items overlap. A 'SPAN' item has the format
            ('SPAN', (sc,sr), (ec,er)) where sc,sr are the IDs of the first (starting) row and column and ec, er are
            the IDs of the last (end) row and column. This function is called for spans that combine cells on the same
            row, so sr=er and we only need to check the column overlap."""
            return min(a[2][0], b[2][0]) - max(a[1][0], b[1][0]) >= 0

        cell_alignment = "RIGHT" if parastyle.alignment in [TA_RIGHT, "RIGHT"] else "LEFT"
        # if metalist[0].metatype == "DYNAMICS":
        #     metalist = sorted(metalist, key=lambda m: "".join(m.positions) + str(m.first_beat) + "".join(m.passes))
        # TODO separate function to group by same position + passes and merge string values if possible.
        for meta in metalist:
            value = formatter(meta, **kwargs)
            # if meta.metatype == "TEMPO":
            # Need to keep track of current tempo
            # self.current_tempo = meta.value
            if not value:
                continue

            parastyle = parastyle or self.template.basicparaStyle
            # Determine the cell id that will contain the text
            cellnr_ = getattr(meta, cellnr) if isinstance(cellnr, str) else cellnr
            cellnr_ = len(colwidths) - 1 if cellnr_ < 0 else cellnr_
            if col_span:
                # Determine the column range (for metadata that apply to multiple columns, such as TEMPO or DYNAMICS).
                # `span` is either number of cells or last cell id, depending on spantype.
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

            # Add 'passes' or 'iterations' information if available
            if "passes" in meta.__class__.model_fields:
                if meta.passes:
                    if any(p for p in meta.passes if p > 0):
                        value += f" (pass {','.join(str(p) for p in meta.passes)})"
            if "iterations" in meta.__class__.model_fields:
                if meta.iterations:
                    if any(p for p in meta.iterations if p > 0):
                        value += f" (iteration {','.join(str(p) for p in meta.iterations)})"

            # merge additional empty cells if necessary to accommondate the text width
            textwidth, _ = self.template.cell_width_height(value.format(dots=""), parastyle=parastyle)
            delta = 2 * self.template.cell_padding_LR
            span_range = col_range
            if span_width(*col_range) < textwidth + delta:
                # Merge the cell with empty adjacent cells if possible until the required width is reached.
                # Use the overflow column if necessary. Expand to the left if the text should be right-aligned.
                step = -1 if cell_alignment == "RIGHT" else 1
                adjacent_cell = span_range[0] if cell_alignment == "RIGHT" else span_range[1]
                while sum(
                    all_colwidths[c] for c in range(min(adjacent_cell, cellnr_), max(adjacent_cell, cellnr_) + 1)
                ) < textwidth + delta and 0 <= adjacent_cell + step < len(all_colwidths):
                    adjacent_cell += step
                if adjacent_cell != cellnr_:
                    span_range = min(adjacent_cell, cellnr_), max(adjacent_cell, cellnr_)
                    cellnr_ = min(adjacent_cell, cellnr_)

            span = None
            if span_range[0] != span_range[1]:
                span = ("SPAN", (span_range[0], len(content.data)), (span_range[1], len(content.data)))

            # Add dots if necessary for metadata spanning more than one beat
            if span_range[0] != span_range[1]:
                freespace = span_width(*span_range) - textwidth - delta
                if getattr(meta, "beat_count", None) and meta.beat_count > 1 and freespace > 0:
                    nrdots = int(freespace / stringWidth("." * 10, parastyle.fontName, parastyle.fontSize) * 10)
                    dots = "." * nrdots
                else:
                    dots = ""
            else:
                dots = ""

            # Determine the required cell height
            available_width = sum(all_colwidths[c] for c in range(span_range[0], span_range[1] + 1))
            _, rowheight = self.template.cell_width_height(
                value.format(dots=dots), parastyle=parastyle, width=available_width
            )

            # Create a new row for the table content
            para = Paragraph(value.format(dots=dots), parastyle)
            row = [para if i == cellnr_ else "" for i in range(len(colwidths))]

            # Check if the current row can be merged with the previous row by determining if their contents overlap.
            # Only merge if the previous row contains metadata.
            if content.data and content.rowtypes[-1] is RowType.METADATA:
                all_styles = cellspans + content.style
                prevrow_spans = [cmd for cmd in all_styles if cmd[0] == "SPAN" and cmd[1][1] == len(content.data) - 1]
                content_overlap = any(cell1 and cell2 for cell1, cell2 in zip(row, content.data[-1]))
                overlapping_spans = span and any(
                    span_overlap(s1, s2) for s1, s2 in itertools.product([span], prevrow_spans)
                )
                if not content_overlap and not overlapping_spans:
                    # Merge the contents of both rows, replace the previous row with the merge result.
                    row = [c1 or c2 for c1, c2 in zip(content.data.pop(), row)]
                    rowheight = max(content.rowheights.pop(), rowheight)
                    if span:
                        span_tolist = list(span)
                        span_tolist[1:] = [(el[0], el[1] - 1) for el in span[1:]]
                        span = tuple(span_tolist)
            if span:
                cellspans.append(span)
            content.append(
                TableContent(
                    data=[row], rowtypes=[RowType.METADATA], colwidths=content.colwidths, rowheights=[rowheight]
                )
            )

        # Update the table style list.
        last_row = len(content.data) - 1
        style_cmds = (
            self.template.metadataTableRAStyle(first_row, last_row)
            if cell_alignment == "RIGHT"
            else self.template.metadataTableLAStyle(first_row, last_row)
        ) + cellspans
        tablestyle = TableStyle(style_cmds)
        content.append(TableContent(colwidths=content.colwidths, style=tablestyle.getCommands()))

        return content

    def _append_comments(self, content: TableContent, comments: list[str]) -> TableContent:
        """Adds comment lines to the content.
        Args:
            content (TableContent): content to which the new rows should be added.
            comments ( list[str]): comment lines.
        """
        for comment in comments:
            if not comment.startswith("#"):
                content.append_empty_row(
                    col_span=[1, -1], rowtype=RowType.COMMENT, parastyle=self.template.basicparaStyle
                )
                content.data[-1][1] = Paragraph(text=html.escape(f"{comment}"), style=self.template.commentStyle)
        return content

    def _append_metadata(self, content: TableContent, gongan: Gongan, above_notation: bool) -> TableContent:
        """Adds the gongan metadata and comments that should appear above or below the notation part.
        Only processes the metadata that is meaningful for the PDF notation. E.g. ValidationMeta,
        GonganMeta, AutoKempyungMeta, OctavateMeta are skipped.
        Args:
            content (TableContent): content to which the new rows should be added
            gongan (Gongan): the gongan to which the metadata belongs
            above_notation (bool): Selects which metadata to generate
        """
        metaclasses = {meta.__class__ for meta in gongan.metadata}
        metadict = {
            metaclass: [meta for meta in gongan.metadata if meta.__class__ == metaclass] for metaclass in metaclasses
        }
        if above_notation:
            # Content that should occur before the notation part of the gongan
            # still to add: SuppressMeta
            if metalist := metadict.get(PartMeta, None):
                content = self._append_single_metadata_type(
                    content, metalist=metalist, **self.template.metaFormatParameters[PartMeta]
                )

            content = self._append_comments(content, gongan.comments)

            for metatype in [TempoMeta, DynamicsMeta, LabelMeta]:
                if metalist := metadict.get(metatype, None):
                    content = self._append_single_metadata_type(
                        content, metalist=metalist, **self.template.metaFormatParameters[metatype]
                    )

        if not above_notation:
            # Content that should occur after the notation part of the gongan
            for metatype in [LoopMeta, GoToMeta, SequenceMeta]:
                if metalist := metadict.get(metatype, None):
                    if metatype is SequenceMeta:
                        content.append_empty_row(
                            col_span=[1, -1], rowtype=RowType.EMPTY, parastyle=self.template.basicparaStyle
                        )  # add an empty row as a separator
                    content = self._append_single_metadata_type(
                        content, metalist=metalist, **self.template.metaFormatParameters[metatype]
                    )

        return content

    def _gongan_colwidths(
        self, staves_dict: dict[tuple[Position, PassID], list[list[Note]]], include_overflow_col: bool
    ) -> list[float]:
        """Calculates the column widths of the given gongan.
        Args:
            staves (dict[Position, list[list[Note]]]): the gongan as a dict Position -> measure
            include_overflow_col: add an extra column at the end that extends to the right margin.
        Returns:
            list[float]: The column widths of the gongans.
        """
        beat_colwidths = None
        for measures in staves_dict.values():
            if not beat_colwidths:
                beat_colwidths = [0] * len(measures)
            for colnr, measure in enumerate(measures):
                text = measure_to_str_rml_safe(measure, self.omit_octave_diacritics, self.octave_diacritics)
                textwidth, _ = self.template.cell_width_height(text, parastyle=self.template.notationStyle)
                beat_colwidths[colnr] = max(beat_colwidths[colnr], textwidth)
            # Determine the remaining available width and assign it to the rightmost column (overflow column)
            # pylint: disable=protected-access
            overflow_colwidth = (
                [max(self.template.doc.pageTemplates[0].frames[0]._aW - sum(beat_colwidths) - self.TAG_COLWIDTH, 0)]
                if include_overflow_col
                else []
            )
            # pylint: enable=protected-access
        colwidths = [self.TAG_COLWIDTH] + beat_colwidths + overflow_colwidth

        return colwidths

    def _staves_to_tabledata(
        self,
        staves_dict: dict[tuple[Position, PassID], list[list[Note]]],
        pos_tags: dict[Position, str],
        gongan_id: int,
        add_overflow_col: bool,
    ) -> list[list[Paragraph]]:
        """Converts the staves of a gongan to a table structure containing a string
           representation of the Note objects.
        Args:
            staves (dict[Position, list[list[Note]]]): the gongan as a dict Position -> measure
            pos_tags (dict[Position, str]): mapping to the string representation of the positions.
        Returns:
            list[list[Paragraph]]: The table structure containing the notation.
        """

        def gongan_id_txt_rml_safe(gid: int, tag: str) -> str:
            """Returns the gongan id as text preceded by as many space chars as necessary to right-aligns
            the id within the cell containing the tag. The gongan id will be appended to the position tag
            of the first stave of the gongan"""
            # Calculate the available width between the position tag and the end of the cell.
            # This is equal to the total cell width minus the width of the position tag.
            tagwidth = stringWidth(tag, self.template.tagStyle.fontName, self.template.tagStyle.fontSize)
            avail_width = self.TAG_COLWIDTH - tagwidth - 2 * self.template.cell_padding_LR
            # Determine the number of characters needed to fill the available width using the
            # gongan id's font size. The font should be monospaced.
            # Then calculate the number of digits of the id and the number of preceding spaces.
            nrcharpos = int(
                10 * avail_width / stringWidth("0" * 10, self.template.gonganIDFontName, self.template.gonganIDFontSize)
            )
            nr_digits = int(math.log10(gid)) + 1
            nrspaces = max(nrcharpos - nr_digits, 0)
            # Create the text. Use non-breaking spaces: reportlab seems to trim regular spaces.
            id_text = self.template.format_text_rml_safe(
                r"&nbsp;" * nrspaces + str(gid), self.template.gonganIdCharStyle
            )
            return id_text

        data = []
        for count, ((position, passid), pos_tag) in enumerate(pos_tags.items()):
            if count == 0:
                # Add gongan numbering next to first position tag
                pos_tag += gongan_id_txt_rml_safe(gongan_id, pos_tag)
            row = [Paragraph(pos_tag, self.template.tagStyle)]
            data.append(row)
            for measure in staves_dict[position, passid]:
                text = measure_to_str_rml_safe(measure, self.omit_octave_diacritics, self.octave_diacritics)
                para = Paragraph(text, self.template.notationStyle) if text else ""
                row.append(para)
            if add_overflow_col:
                row.append("")
        return data

    def _convert_to_pdf(self) -> None:  # score_validation
        """Converts a score object to readable notation and saves it to PDF format.
        Args:
            score (Score): The score
        """
        # Save global comments
        # pylint: disable=protected-access
        colwidths = [self.TAG_COLWIDTH] + [self.template.doc.pageTemplates[0].frames[0]._aW - self.TAG_COLWIDTH]
        # pylint: enable=protected-access
        content: TableContent = TableContent(data=[], colwidths=colwidths, style=[], template=self.template)
        self._append_comments(content, comments=self.score.global_comments)
        if content.data:
            comment_table = self.template.create_table(content)
            self.story.append(comment_table)

        for gongan in self.gongan_iterator(self.score):
            if not gongan.beats:
                continue

            # Determine the column widths
            staves_dict = clean_staves(gongan)
            colwidths = self._gongan_colwidths(staves_dict, include_overflow_col=True)

            # Create an empty content container and add the metadata that should appear above
            # the gongan notation
            content = TableContent(data=[], colwidths=colwidths, style=[], template=self.template)
            content = self._append_metadata(content, gongan=gongan, above_notation=True)

            # Add the gongan notation
            pos_tags = aggregate_positions(gongan)
            notation_data = self._staves_to_tabledata(staves_dict, pos_tags, gongan.id, add_overflow_col=True)
            if notation_data:
                row1, row2 = len(content.data), len(content.data) + len(notation_data) - 1
                content.append(
                    TableContent(
                        data=notation_data,
                        rowtypes=[RowType.NOTATION] * len(notation_data),
                        colwidths=colwidths,
                        rowheights=[self.template.notation_row_height + self.template.cell_padding_TB * 2]
                        * len(notation_data),
                        # If gongan has no kempli beat, the beats will be separated by dotted lines.
                        style=(
                            self.template.notationTableStyle(row1, row2)
                            if has_kempli_beat(gongan)
                            else self.template.notationNoKempliTableStyle(row1, row2)
                        ),
                        template=self.template,
                    )
                )

            # Add the metadata that should appear below gongan notation
            content = self._append_metadata(content, gongan, above_notation=False)

            # Create and append the gongan table
            if content.data:
                gongan_table = self.template.create_table(content)
                self.story.append(gongan_table)
        self.template.doc.build(self.story)

    @override
    def _main(self):
        """Main method, creates the PDF notation file"""
        self._convert_to_pdf()
        self.logger.info("Notation file saved as %s", self.template.filepath)
        if self.has_errors:
            return None
        return self.score.settings.pdf_out_file


if __name__ == "__main__":
    pass
