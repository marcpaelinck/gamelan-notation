"""
Parses the notation into a dict structure.
The parser uses the Tatsu library in combination with a Parser Expression Grammar (PEG).
The grammar used can be found in ./data/grammars.
PEG: https://en.wikipedia.org/wiki/Parsing_expression_grammar
Tatsu: https://tatsu.readthedocs.io/en/stable/intro.html

The following structure is returned:

<score> :: { <gongan id>: int -> <gongan> }
<gongan> :: { METADATA -> [ <metadata>: MetaData ], COMMENTS -> [ <comment>: str ], BEATS -> <beats> }
<beats> :: { <beat id>: int -> <beat> }
<beat> :: { <position>: Position -> <measure>: Measure(position: Position, passes: <passes>) }
<passes> :: { <pass id>: int ->  <note list>: Measure.Pass(pass_seq: int, line: int, notes: <notes>) }
<notes>: [ <note>: Note ]

<gongan id>, <beat id> and <pass id> are cast into a NamedIntID class, which is an int subclass that
formats the values with a label: LABEL(<value>). This makes the structure more legible and makes debugging easier.

METADATA, COMMENTS, BEATS: ParserTag

Example:

{   SCORE LEVEL(-1):    {   METADATA:   [MetaData(...), ...],
                            COMMENTS:   ['comment 1', ...],
                            BEATS:      [],  # no beats on score level
                        }
    GONGAN(1):          {   METADATA:   [MetaData(...), ...],
                            COMMENTS:   ['comment 2', ...],
                            BEATS       {
                                BEAT(1):    {
                                    UGAL: Measure(
                                            position=KANTILAN_SANGSIH,
                                            passes={
                                                DEFAULT PASS(-1):
                                                    Measure.Pass(
                                                        pass_seq=DEFAULT PASS(-1),
                                                        line=9,
                                                        notes=[Note(...), Note(...), ...]
                                                    ),
                                                PASS(1):
                                                    ...
                                            }
                                    },
                                    CALUNG: { ...
                                    },
                                        ...
                                },
                                BEAT(2):    {...
                                },
                            }
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
from typing import Any

from tatsu import compile as tatsu_compile
from tatsu.exceptions import FailedParse
from tatsu.model import ParseModel
from tatsu.util import asjson

from src.common.classes import InstrumentTag, Measure, Notation, Note
from src.common.constants import NotationDict, ParserTag, Position, RuleType
from src.notation2midi.classes import (
    MetaDataRecord,
    NamedIntID,
    NoteRecord,
    ParserModel,
)
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


class BeatID(NamedIntID):
    name = "BEAT"


class PassID(NamedIntID):
    name = "PASS"
    default = "DEFAULT PASS"


# pylint enable=missing-class-docstring


class NotationTatsuParser(ParserModel):
    """Parser that converts notation documents into a hierarchical dict structure. It uses the
    Tatsu library in combination with ebnf grammar files.
    The parser has no 'knowledge' about the instruments and idiom of the music. It only checks the
    basic structure of the notation as described in the grammar files and reports any syntax error.
    """

    run_settings: RunSettings
    grammar_model: str
    model_source: str
    _char_to_fontinfo_dict: dict[str, dict[str, Any]]
    _symbol_to_note: dict[str, NoteRecord]

    def __init__(self, run_settings: RunSettings):
        super().__init__(self.ParserType.NOTATIONPARSER, run_settings)
        self.run_settings = run_settings
        self.grammar_model = self._create_notation_grammar_model(self.run_settings, from_pickle=False, pickle_it=False)
        # Initialize _font_dict lookup dict
        self._char_to_fontinfo_dict = {sym[FontFields.SYMBOL]: sym for sym in self.run_settings.data.font}
        # Initialize _symbol_to_note lookup dict
        note_records = get_note_records(self.run_settings)
        self._symbol_to_note = {
            self.sorted_chars(note[NoteFields.SYMBOL]): NoteRecord(
                **{k: v for k, v in note.items() if k in NoteRecord.fieldnames()}
            )
            for note in note_records
        }

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
        # other parameters + values. E.g.
        # {"meta": "DYNAMICS", "value": "f", "parameters": [{"positions": ["gangsa"]}, {"first_beat": 13}]}
        # We need to flatten this structure before parsing it into a MetaData object.
        parms = metadict.get("parameters", [])
        flattened_dict = {k: v for k, v in metadict.items() if k not in ["meta", "parameters"]} | dict(
            ChainMap(*(parms if isinstance(parms, list) else [parms]))
        )
        return flattened_dict

    def _parse_generic_note(
        self,
        symbol: str,
        position: Position,
    ) -> "Note":
        """Parses the given notation symbol to a NoteRecord object.
           The note is generic in the sense that it is not bound to an instument type.
           This binding will be performed in a later step of the pipeline (dict_to_score).
           This is done to keep the notation parser free of any 'knowledge' about the instruments.
        Args:
            symbol (str): notation characters.
            position (Position): position
        Returns:
            NoteRecord: A generic note object, i.e. not bound to any instrument type.
        """
        normalized_symbol = self.sorted_chars(symbol)

        if len(symbol) < 1:
            raise ValueError(f"Unexpected empty symbol for {position}")
        return self._symbol_to_note[normalized_symbol]

    def _parse_measure(self, measure: str, position: Position) -> list[Note]:
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
                next_note = self._parse_generic_note(note_chars, position)
            except ValueError as e:
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
        additional_staves = []
        for stave in staves:
            tag = stave[ParserTag.POSITION][ParserTag.TAG]
            positions = stave[ParserTag.ALL_POSITIONS] = InstrumentTag.get_positions(tag)
            pass_sequence = PassID(int(stave[ParserTag.POSITION][ParserTag.PASS]))
            stave[ParserTag.POSITION] = positions[0]
            stave[ParserTag.PASS] = pass_sequence
            for position in stave[ParserTag.ALL_POSITIONS][1:]:
                # Create a copy of the stave for each additional position
                newstave = copy.deepcopy(stave)
                newstave[ParserTag.POSITION] = position
                newstave[ParserTag.PASS] = pass_sequence
                additional_staves.append(newstave)
        staves.extend(additional_staves)

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

    def _staves_to_beats(self, staves: list[dict]) -> list[dict]:
        """Transposes the stave -> beats structure of a gongan to beat -> staves
            target structure is: gongan[beat_id][position][passes]
        Args:
            staves (list[dict]): staves belonging to the same gongan.

        Returns:
            list[dict]: the transposed structure
        """
        if not staves:
            return {}
        # There can be multiple staves with the same `position` value. In that case they will have different `pass`
        # values. The staves first need to be grouped by position. We create a position dict for this, will also
        # be used below to retrieve the correct ALL_POSITIONS value when a new Measure is created.
        position_dict = {stave[ParserTag.POSITION]: stave[ParserTag.ALL_POSITIONS] for stave in staves}
        staves_by_pos_pass = {
            position: {int(stave[ParserTag.PASS]): stave for stave in staves if stave[ParserTag.POSITION] == position}
            for position in position_dict.keys()
        }
        # count only non-empty beats
        beat_count = max(len([beat for beat in stave[ParserTag.BEATS] if beat]) for stave in staves)
        beats = {
            BeatID(beat_seq + 1): {
                position: Measure(
                    position=position,
                    all_positions=position_dict[position],  # positions,
                    passes={
                        stave[ParserTag.PASS]: (
                            Measure.Pass(
                                seq=stave[ParserTag.PASS],
                                line=stave[ParserTag.LINE],
                                notes=(
                                    stave[ParserTag.BEATS][beat_seq] if beat_seq < len(stave[ParserTag.BEATS]) else []
                                ),
                                ruletype=RuleType.UNISONO if len(stave[ParserTag.ALL_POSITIONS]) > 1 else None,
                                autogenerated=False,
                            )
                        )
                        for pass_, stave in position_staves.items()
                    },
                )
                for position, position_staves in staves_by_pos_pass.items()
            }
            for beat_seq in range(beat_count)
        }

        return beats

    @ParserModel.main
    def parse_notation(self, notation: str | None = None) -> NotationDict:
        """parses the notation into a record structure. The entire document is parsed.
           If a parsing error is encountered, the error is logged and the parser skips
           to the next line.
        Args:
            notation (str | None, optional): the notation read from file. Defaults to None.
        Returns:
            NotationDict: dict containing a structured representation of the notation.
            See the beginning of this module for a description.
        """
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
                stave for stave in gongan.get(ParserTag.STAVES, {}) if any((beat for beat in stave["beats"]))
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
                del stave[ParserTag.STAVES]  # remove superfluous key
                # Parse the beats into Note objects
                parsed_beats = []
                for self.curr_beat_id, measure in enumerate(stave[ParserTag.BEATS], start=1):
                    parsed_beats.append(self._parse_measure(measure, stave[ParserTag.POSITION]))
                stave[ParserTag.BEATS] = parsed_beats

            # Transpose the gongan from stave-oriented to beat-oriented
            gongan[ParserTag.BEATS] = self._staves_to_beats(gongan[ParserTag.STAVES])
            del gongan[ParserTag.STAVES]
        # self._update_grace_notes(notation_dict)

        if self.has_errors:
            self.logerror("Program halted.")
            exit()

        notation = Notation(notation_dict=notation_dict, settings=self.run_settings)

        return notation


if __name__ == "__main__":
    settings = Settings.get()
    parser = NotationTatsuParser(settings)
    print(parser.sorted_chars("i=,/"))
