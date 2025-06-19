"""
Parses the notation into a dict structure.
The parser uses the Tatsu library in combination with a Parser Expression Grammar (PEG).
The grammar used can be found in ./data/grammars.
PEG: https://en.wikipedia.org/wiki/Parsing_expression_grammar
Tatsu: https://tatsu.readthedocs.io/en/stable/intro.html

The following structure is returned:

<score> :: { <gongan id>: int -> <gongan> }
<gongan> :: { METADATA -> [ <metadata> :: MetaData ], COMMENTS -> [ <comment> :: str ], STAVES -> <staves> }
<staves> :: [ <stave> ]
<stave> :: {PASS -> int, MEASURES -> <notes>, POSITION -> <position>, ALL_POSITIONS -> <positions>, LINE -> int }
<positions> :: [ <position> ]
<position> :: Position
<notes> :: [ <note> ]
<note> :: Note

<gongan id>, <beat id> and <pass id> are cast into a NamedIntID class, which is an int subclass that
formats the values with a label: LABEL(<value>). This makes the structure more legible and makes debugging easier.

METADATA, COMMENTS, STAVES, MEASURES, ALL_POSITIONS, PASS: ParserTag

Example:

{   SCORE LEVEL(-1):    {   METADATA:   [MetaData(...), ...],
                            COMMENTS:   ['comment 1', ...],
                            STAVES:      [],  # no beats on score level
                        },
    GONGAN(1):          {   METADATA:   [MetaData(...), ...],
                            COMMENTS:   ['comment 2', ...],
                            STAVES:      [
                                            {
                                                PASS: DEFAULT_PASS(-1),
                                                MEASURES, [[Note(...), Note(...), ...], [Note(...), Note(...), ...], ....],
                                                POSITION: REYONG_1,
                                                ALL_POSITIONS: [REYONG_1, REYONG_2, REYONG_3, REYONG_4],
                                                LINE: 12,
                                            },
                                            ...
                                        ],
                                        ...
                        },
    GONGAN(2):          { ...
                        },
    ...
}
"""

import copy
import json
import pickle
import re
import sys
from collections import ChainMap
from typing import Any, override

from tatsu import compile as tatsu_compile
from tatsu.exceptions import FailedParse
from tatsu.model import ParseModel
from tatsu.util import asjson

from src.common.classes import InstrumentTag, Notation
from src.common.constants import NotationDict, NotationFontVersion, ParserTag, Position
from src.common.notes import Note, UnboundNote
from src.notation2midi.classes import Agent, MetaDataRecord, NamedIntID
from src.settings.classes import RunSettings
from src.settings.constants import FontFields, NoteFields
from src.settings.font_to_valid_notes import get_note_records
from src.settings.settings import Settings

# The following classes display meaningful names for the IDs
# which will be used as key values in the output dict structure.
# Mostly useful for debugging purposes.


# pylint: disable=missing-class-docstring
class GonganID(NamedIntID):
    name = "GONGAN"
    default = "SCORE LEVEL"


class PassID(NamedIntID):
    name = "PASS"
    default = "DEFAULT PASS"


# pylint enable=missing-class-docstring


class NotationParserAgent(Agent):
    """Parser that converts notation documents into a hierarchical dict structure. It uses the
    Tatsu library in combination with ebnf grammar files.
    The parser has no 'knowledge' about the instruments and idiom of the music. It only checks the
    basic structure of the notation as described in the grammar files and reports any syntax error.
    """

    AGENT_TYPE = Agent.AgentType.NOTATIONPARSER
    EXPECTED_INPUT_TYPES = (Agent.InputOutputType.RUNSETTINGS,)
    RETURN_TYPE = Agent.InputOutputType.NOTATION

    run_settings: RunSettings
    grammar_model: str
    model_source: str
    _char_to_fontinfo_dict: dict[str, dict[str, Any]]
    _symbol_to_note: dict[str, UnboundNote]

    def __init__(self, run_settings: RunSettings):
        super().__init__(run_settings)
        self.run_settings = run_settings
        self.grammar_model = self._create_notation_grammar_model(self.run_settings, from_pickle=False, pickle_it=False)
        # Initialize _font_dict lookup dict
        self._char_to_fontinfo_dict = {sym[FontFields.SYMBOL]: sym for sym in self.run_settings.data.font}
        # Initialize _symbol_to_note lookup dict
        note_records = get_note_records(self.run_settings)
        self._symbol_to_note = {
            self.sorted_chars(note[NoteFields.SYMBOL]): UnboundNote(
                **{k: v for k, v in note.items() if k in UnboundNote.fieldnames()}
            )
            for note in note_records
        }

    @override
    @classmethod
    def run_condition_satisfied(cls, run_settings: RunSettings):
        return True

    def sorted_chars(self, chars: str) -> str:
        """Sorts the characters of a note symbol in a unique and deterministic order.
        The sorting order is determined by the sequence of the Modifier Enum value of each font character.
        The resulting string starts with the pitch character (Modifier.NONE) followed by optional
        modifier in a fixed sequence."""
        try:
            return "".join(sorted(chars, key=lambda c: self._char_to_fontinfo_dict[c][FontFields.MODIFIER].sequence))
        except KeyError:
            self.logerror("Illegal character in %s", chars)
        except Exception:  # pylint: disable=broad-exception-caught
            self.logerror("Error parsing note %s", chars)

    @classmethod
    def unoctavated(cls, note_chars: str) -> str:  # TODO MOVE
        """returns a note symbol with octavation characters removed."""
        # TODO: make this more generic
        return note_chars.replace(",", "").replace("<", "")

    def _create_notation_grammar_model(
        self, run_settings: RunSettings, from_pickle: bool = False, pickle_it: bool = False
    ) -> ParseModel:
        # Read and compile the grammar
        if from_pickle:
            self.model_source = "model from pickled file"
            with open(run_settings.grammar.pickle_filepath, "rb") as picklefile:
                grammar_model = pickle.load(picklefile)
        else:
            self.model_source = "model compiled from grammar files"
            with open(run_settings.grammar.notation_filepath, "r", encoding="utf-8") as grammarfile:
                notation_grammar = grammarfile.read()
            grammar_model = tatsu_compile(notation_grammar)
        if pickle_it:
            self.loginfo("Saving parser model to pickle file.")
            with open(run_settings.grammar.pickle_filepath, "wb") as picklefile:
                pickle.dump(grammar_model, picklefile)
        return grammar_model

    def _flatten_meta(self, metadict: dict) -> dict:
        # The json_dict contains the first parameter and its value, and a key "parameters" with a list of dicts
        # containing the other parameters + values. E.g.
        # {"meta": "DYNAMICS", "value": "f", "parameters": [{"positions": ["gangsa"]}, {"first_beat": 13}]}
        # We need to flatten this structure before parsing it into a MetaData object.
        parms = metadict.get("parameters", [])
        flattened_dict = {k: v for k, v in metadict.items() if k not in ["meta", "parameters"]} | dict(
            ChainMap(*(parms if isinstance(parms, list) else [parms]))
        )
        return flattened_dict

    def _parse_unbound_note(
        self,
        symbol: str,
        position: Position,
    ) -> UnboundNote:
        """Parses the given notation symbol to an UnboundNote object.
           No check is performed whether the note belongs to the instrument's range. Range check and
           casting of the notes to their instrument's range will be performed  in a later step down the pipeline.
        Args:
            symbol (str): notation characters.
            position (Position): position
        Returns:
            UnboundNote: A generic note object, i.e. not bound to any instrument type.
        """
        normalized_symbol = self.sorted_chars(symbol)

        if len(symbol) < 1:
            raise ValueError(f"Unexpected empty symbol for {position}")
        return self._symbol_to_note[normalized_symbol]

    def _parse_measure(self, measure: str, position: Position) -> list[Note]:
        # TODO review this documentation
        """Parses the notation of a stave to note objects
           If the stave stands for multiple reyong positions, the notation is transformed to match
           each position separately. There are two possible cases:
            - REYONG_1 and REYONG_3 are combined: the notation is expected to represent the REYONG_1 part
              and the score is octavated for the REYONG_3 position.
            - REYONG_2 and REYONG_4: similar case. The notation should represent the REYONG_2 part.
            - All reyong positions: the notation is expected to represent the REYONG_1 part.
              In this case the kempyung equivalent of the notation will be determined for REYONG_2
              and REYONG_4 within their respective range.
        Args:
            stave (str): one stave of notation
            position (Position):
            multiple_positions (list[Position]): List of all positions for this stave.
        Returns: list[str] | None: _description_
        """
        notes = []  # will contain the Note objects
        note_chars = measure
        for note_chars in measure:
            try:
                next_note = self._parse_unbound_note(note_chars, position)
            except (ValueError, KeyError) as e:
                self.logerror(str(e))
            if not next_note:
                self.logerror(f"Could not parse {note_chars[0]} from {measure} for {position.value}")
                note_chars = note_chars[1:]
            else:
                notes.append(next_note)
                note_chars = note_chars[len(next_note.symbol) :]
        return notes

    def _replace_metadata_tags_with_positions(self, metadata_list: list[dict]) -> None:
        """Translates the values of `position` or `positions` metadata attributes to a list of Position enum values.
           Note that a tag can represent multiple values, e.g. 'gangsa' stands for four positions: polos and sangsih
           positions for both pemade and kantilan.
        Args:
            metadata_list (list[dict]): list of records, each representing a metadata item
        """
        for meta in metadata_list:
            if "positions" in meta:
                meta["positions"] = sum([InstrumentTag.get_positions(tag) for tag in meta["positions"]], [])
            if "parameters" in meta:
                if "positions" in meta["parameters"]:
                    meta["parameters"]["positions"] = sum(
                        [InstrumentTag.get_positions(tag) for tag in meta["parameters"]["positions"]], []
                    )

    def _replace_stave_tags_with_positions(self, staves: list[dict]) -> None:
        """Translates the tag (position name in the first column of a measure) to a list of Position enum values.
           Note that a tag can represent multiple values, e.g. 'gangsa' stands for four positions: polos and sangsih
           positions for both pemade and kantilan.
        Args:
            staves (list[dict]): list of records, each representing a stave
        """

        def split_passes(pass_tag: str | int) -> list[int]:
            if isinstance(pass_tag, int):
                return [pass_tag]
            passes = [int(p) for p in pass_tag.split("-")]
            return [PassID(p) for p in range(passes[0], passes[-1] + 1)]

        multiple_staves = []
        for stave in staves:
            tag = stave[ParserTag.POSITION][ParserTag.TAG]
            stave[ParserTag.ALL_POSITIONS] = InstrumentTag.get_positions(tag)
            pass_sequences = split_passes(stave[ParserTag.POSITION][ParserTag.PASS])
            for position in stave[ParserTag.ALL_POSITIONS]:
                for pass_seq in pass_sequences:
                    # Create a copy of the stave for each additional position
                    newstave = copy.deepcopy(stave)
                    newstave[ParserTag.POSITION] = position
                    newstave[ParserTag.PASS] = pass_seq
                    multiple_staves.append(newstave)
        staves.clear()
        staves.extend(multiple_staves)

    def _passes_str_to_list(self, rangestr: str) -> list[int]:
        """Converts a pass indicator following a position tag to a list of passes.
            A colon (:) separates the position tag and the pass indicator.
            The indicator has one of the following formats:
            <pass>[,<pass>...]
            <firstpass>-<lastpass>
            where <pass>, <firstpass> and <lastpass> are single digits.
            e.g.:
            gangsa p:2,3
            reyong:1-3

        Args:
            rangestr (str): the pass range indicator, in the prescribed format.

        Raises:
            ValueError: string does not have the expected format.

        Returns:
            list[int]: a list of passes (passes are numbered from 1)
        """
        if not re.match(r"^(\d-\d|(\d,)*\d)$", rangestr):
            raise ValueError(f"Invalid value for passes: {rangestr}")
        if re.match(r"^\d-\d$", rangestr):
            return list(range(int(rangestr[0]), int(rangestr[2]) + 1))
        else:
            return list(json.loads(f"[{rangestr}]"))

    @override
    def _main(self, notation: str | None = None) -> NotationDict:
        """parses the notation into a record structure. The entire document is parsed.
           If a parsing error is encountered, the error is logged and the parser skips
           to the next line.
        Args:
            notation (str | None, optional): the notation read from file. Defaults to None.
        Returns:
            NotationDict: dict containing a structured representation of the notation.
            See the beginning of this module for a description.
        """
        if not self.run_settings.fontversion is NotationFontVersion.BALIMUSIC5:
            self.logerror("Cannot parse font %s.", self.run_settings.fontversion)
            return None

        if notation:
            self.loginfo("Parsing notation from string")
        else:
            notationpath = self.run_settings.notation_filepath
            # pylint disable=too-many-function-args
            self.loginfo("Parsing file %s", notationpath)
            try:
                with open(notationpath, mode="r", encoding="utf-8") as notationfile:
                    notation = notationfile.read()
            except ValueError as e:
                self.logerror(str(e))
                sys.exit()

        # Parse the notation using the ebnf grammar.
        # In case of an error, the current line will be skipped and the parser will be called again
        # on the remaining lines to log possible additional errors. In that case the value of ast
        # will be incomplete, therefore the program will halt after parsing the remainder of the file.
        # The reason for this approach is that the -> `skip to` in combination with ^`` alert grammar
        # statement does not work as expected:
        # - The alert is not added to the node's parseinfo list but becomes part of the parsed expression.
        # - The alert logging misses the accuracy and relevance of the parser's error messages.
        self.loginfo(f"Using {self.model_source}.")
        ast = None
        line_offset = 0
        while not ast:
            try:
                ast = self.grammar_model.parse(notation)
            except FailedParse as e:
                parsed_text = e.args[0].original_text[: e.pos + 1]
                char = parsed_text[e.pos]
                if char == "\n":
                    parsed_text = parsed_text[:-1]
                self.curr_line_nr = parsed_text.count("\n") + line_offset + 1
                start_curr_line = parsed_text.rfind("\n") + 1  # rfind returns -1 if not found
                chars_to_next_line = e.args[0].original_text[start_curr_line:].find("\n") + 1
                char_pos = e.pos - start_curr_line + 1
                char = char.replace("\n", "end of line").replace("\t", "tab")
                self.logerror(
                    "Unexpected `%s` at position %s. %s. Ignoring the rest of the line.", char, char_pos, e.message
                )
                if e.pos == 0 or chars_to_next_line < 0:
                    # No progress or nothing to do
                    break
                line_offset = self.curr_line_nr
                notation = e.args[0].original_text[start_curr_line + chars_to_next_line :]

        if self.has_errors:
            self.logerror("Program halted.")
            exit()

        notation_dict = asjson(ast)

        # Convert the gongan structure into a dict {id: gongan}
        # The sum function concatenates the final gongan to the list of gongans
        # (final gongan is defined separately in the grammar)
        notation_dict = {GonganID(-1): notation_dict[ParserTag.UNBOUND]} | {
            GonganID(count + 1): gongan
            for count, gongan in enumerate(notation_dict[ParserTag.GONGANS])
            # GonganID(count + 1): gongan for count, gongan in enumerate(sum(notation_dict[ParserTag.GONGANS][0], []))
        }

        # group items by category: comment, metadata and staves
        # Add line number to MetaData and Stave dicts
        notation_dict = {
            gongan_id: {
                key: [
                    (
                        element[key].rstrip("\t ")
                        if key is ParserTag.COMMENTS
                        else element[key] | {ParserTag.LINE: element[ParserTag.PARSEINFO][ParserTag.ENDLINE]}
                    )
                    for element in gongan
                    if key.value in element.keys()
                ]
                for key in [ParserTag.COMMENTS, ParserTag.METADATA, ParserTag.STAVES]
            }
            for gongan_id, gongan in notation_dict.items()
        }

        # Flatten the metadata items, create MetaData and Note objects

        for self.curr_gongan_id, gongan in notation_dict.items():
            # Remove empty staves so that they can be recognized as 'missing staves' by the dict to score parser.
            gongan[ParserTag.STAVES] = [
                stave
                for stave in gongan.get(ParserTag.STAVES, {})
                if any((measure for measure in stave[ParserTag.MEASURES]))
            ]

            # Parse the metadata into MetaDataRecord objects
            gongan[ParserTag.METADATA] = [self._flatten_meta(meta) for meta in gongan[ParserTag.METADATA]]
            try:
                self._replace_metadata_tags_with_positions(gongan[ParserTag.METADATA])
            except ValueError as err:
                self.logerror(str(err))
                continue
            try:
                gongan[ParserTag.METADATA] = [MetaDataRecord(**meta) for meta in gongan[ParserTag.METADATA]]
            except ValueError as err:
                self.logerror(str(err))
                continue

            # Look up the Position value for the 'free style' tags.
            # If the tag stands for multiple posiitions, create a copy of the stave for each position.
            try:
                self._replace_stave_tags_with_positions(gongan[ParserTag.STAVES])
            except ValueError as err:
                self.logerror(str(err))
                continue

            for stave in gongan[ParserTag.STAVES]:
                self.curr_line_nr = stave[ParserTag.LINE]

                # Replace string key values with ParserTag values
                for key in [ParserTag.LINE, ParserTag.POSITION, ParserTag.MEASURES, ParserTag.PARSEINFO]:
                    stave[key] = stave.pop(key)
                # remove superfluous key
                del stave[ParserTag.STAVES]
                # Parse and cast the measures into Note objects
                # TODO: it would be better to only parse the mearsures into character groups, each
                # representing a single note, and to leave the casting into Notes for the score creator.
                parsed_measures = []
                for self.curr_measure_id, measure in enumerate(stave[ParserTag.MEASURES], start=1):
                    parsed_measures.append(self._parse_measure(measure, stave[ParserTag.POSITION]))
                stave[ParserTag.MEASURES] = parsed_measures

        self.abort_if_errors()
        notation = Notation(notation_dict=notation_dict, settings=self.run_settings)

        return notation


if __name__ == "__main__":
    settings = Settings.get()
    parser = NotationParserAgent(settings)
    print(parser.sorted_chars("i=,/"))
