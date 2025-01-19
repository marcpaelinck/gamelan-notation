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
import pickle
from collections import ChainMap

from tatsu import compile
from tatsu.model import ParseModel
from tatsu.util import asjson

from src.common.classes import InstrumentTag, Measure, Notation, Note
from src.common.constants import NotationDict, ParserTag, Position, Stroke
from src.common.metadata_classes import MetaData, Scope
from src.notation2midi.classes import NamedIntID, ParserModel
from src.notation2midi.special_notes_treatment import (
    generate_tremolo,
    get_nearest_note,
    update_grace_notes_octaves,
)
from src.settings.classes import RunSettings
from src.settings.settings import get_run_settings

# The following classes display meaningful names for the IDs
# which will be used as key values in the output dict structure.
# Mostly useful for debugging purposes.


class GonganID(NamedIntID):
    name = "GONGAN"
    default = "SCORE LEVEL"


class BeatID(NamedIntID):
    name = "BEAT"


class PassID(NamedIntID):
    name = "PASS"
    default = "DEFAULT PASS"


class NotationTatsuParser(ParserModel):
    run_settings: RunSettings
    grammar_model: str
    model_source: str

    def __init__(self, run_settings: RunSettings):
        super().__init__(self.ParserType.NOTATIONPARSER, run_settings)
        self.run_settings = run_settings
        self.grammar_model = self._create_notation_grammar_model(self.run_settings, from_pickle=False, pickle_it=False)

    def _create_notation_grammar_model(
        self, settings: RunSettings, from_pickle: bool = False, pickle_it: bool = False
    ) -> ParseModel:
        # Read and compile the grammar
        if from_pickle:
            self.model_source = "model from pickled file"
            with open(settings.grammars.pickle_filepath, "rb") as picklefile:
                grammar_model = pickle.load(picklefile)
        else:
            self.model_source = "model compiled from grammar files"
            with open(settings.grammars.notation_filepath, "r") as grammarfile:
                notation_grammar = grammarfile.read()
            grammar_model = compile(notation_grammar)
        if pickle_it:
            self.loginfo("Saving parser model to pickle file.")
            with open(settings.grammars.pickle_filepath, "wb") as picklefile:
                pickle.dump(grammar_model, picklefile)
        return grammar_model

    def _import_notation(self, settings: RunSettings):
        # Read and parse the notation file
        with open(settings.notation.filepath, "r") as notationfile:
            notation = notationfile.read()
        return notation

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

    def _parse_stave(self, stave: str, position: Position) -> list[Note]:
        """Parses the notation of a stave to note objects

        Args:
            stave (str): one stave of notation
            position (Position):

        Returns: str | None: _description_
        """
        notes = []  # will contain the Note objects
        tremolo_notes = []
        note_chars = stave
        while note_chars:
            # try parsing the next note
            next_note = Note.parse_next_note(note_chars, position)
            if not next_note:
                self.logerror(f" {position.value} {stave} has invalid {note_chars[0]}")
                note_chars = note_chars[1:]
            else:
                if istremolo := (next_note.stroke in (Stroke.TREMOLO, Stroke.TREMOLO_ACCELERATING)):
                    tremolo_notes.append(next_note)
                if len(tremolo_notes) == 2 or (
                    tremolo_notes and (not istremolo or len(note_chars) == len(next_note.symbol))
                ):
                    notes.extend(generate_tremolo(tremolo_notes, self.run_settings.midi, self.logerror))
                    tremolo_notes.clear()
                if not istremolo:
                    notes.append(next_note)
                note_chars = note_chars[len(next_note.symbol) :]

        return notes

    def _explode_tags(self, staves: list[dict]) -> list[dict]:
        additional_staves = []
        for stave in staves:
            positions = InstrumentTag.get_positions(stave[ParserTag.POSITION][ParserTag.TAG])
            pass_seq = PassID(int(stave[ParserTag.POSITION][ParserTag.PASS]))
            stave[ParserTag.POSITION] = positions[0]
            stave[ParserTag.PASS] = pass_seq
            if len(positions) > 1:
                for position in positions[1:]:
                    newstave = copy.deepcopy(stave)
                    newstave[ParserTag.POSITION] = position
                    newstave[ParserTag.PASS] = pass_seq
                    additional_staves.append(newstave)
        staves.extend(additional_staves)

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
        # count only non-empty beats
        beat_count = max(len([beat for beat in stave[ParserTag.BEATS] if beat]) for stave in staves)
        positions = {stave[ParserTag.POSITION] for stave in staves}
        beats = {
            BeatID(beat_seq + 1): {
                position: Measure(
                    position=position,
                    passes={
                        stave[ParserTag.PASS]: (
                            Measure.Pass(
                                seq=stave[ParserTag.PASS],
                                line=stave[ParserTag.LINE],
                                notes=(
                                    stave[ParserTag.BEATS][beat_seq] if beat_seq < len(stave[ParserTag.BEATS]) else []
                                ),
                            )
                        )
                        for stave in staves
                        if stave[ParserTag.POSITION] == position
                    },
                )
                for position in positions
                if any(stave for stave in staves)
            }
            for beat_seq in range(beat_count)
        }

        return beats

    def _update_grace_notes(self, notation_dict: NotationDict):
        """Modifies the octave of all the grace notes to match the not that follows.
        Args:
            notation_dict (NotationDict): The notation
        """

        for self.curr_gongan_id, beat_dict in notation_dict.items():
            for self.curr_beat_id, measures in beat_dict[ParserTag.BEATS].items():
                # if not isinstance(self.curr_beat_id, int):
                #     continue
                for position, measure in measures.items():
                    for pass_seq, notelist in measure.passes.items():
                        update_grace_notes_octaves(
                            notes=notelist.notes, group=self.run_settings.instruments.instrumentgroup
                        )

    def parse_notation(self, notation: str | None = None) -> NotationDict:
        if notation:
            self.loginfo(f"Parsing notation from string")
        else:
            notationpath = self.run_settings.notation.filepath
            self.loginfo(f"Parsing file {notationpath}")
            with open(notationpath, "r") as notationfile:
                notation = notationfile.read()

        # Parse the notation using the ebnf grammar.
        self.loginfo(f"Using {self.model_source}.")
        ast = None
        line_offset = 0
        while not ast:
            try:
                ast = self.grammar_model.parse(notation)
            except Exception as e:
                parsed_text = e.args[0].original_text[: e.pos + 1]
                self.curr_line_nr = parsed_text.count("\n") + line_offset + 1
                start_curr_line = parsed_text.rfind("\n") + 1  # rfind returns -1 if not found
                start_next_line = e.args[0].original_text[start_curr_line:].find("\n") + 1
                char = parsed_text[e.pos]
                char_pos = e.pos - start_curr_line + 1
                self.logerror(
                    f"Unexpected character `{char}` at position {char_pos}. {e.message}. Ignoring the rest of the line."
                )
                if e.pos == 0 or start_next_line < 0:
                    # No progress or nothing to do
                    return None
                else:
                    line_offset = self.curr_line_nr
                    notation = e.args[0].original_text[e.pos + 1 + start_next_line :]

        if self.has_errors:
            self.logerror("Program halted.")
            exit()

        notation_dict = asjson(ast)

        # Convert the gongan structure into a dict {id: gongan}
        # The sum function concatenates the final gongan to the list of gongans (final gongan is defined separately in the grammar)
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
                        element[key]
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
        for gongan in notation_dict.values():
            # Remove empty staves so that they can be recognized as 'missing staves' by the dict to score parser.
            gongan[ParserTag.STAVES] = [
                stave for stave in gongan.get(ParserTag.STAVES, {}) if any((beat for beat in stave["beats"]))
            ]

            # Parse the metadata into MetaData objects
            gongan[ParserTag.METADATA] = [
                MetaData(data=self._flatten_meta(meta)) for meta in gongan[ParserTag.METADATA]
            ]
            for metadata in gongan[ParserTag.METADATA]:
                if metadata.data.scope == Scope.SCORE:
                    gongan[ParserTag.METADATA].remove(metadata)
                    notation_dict[GonganID.default_value][ParserTag.METADATA].append(metadata)

            # Explode staves with an instrument tag that represents multiple instruments
            self._explode_tags(gongan[ParserTag.STAVES])
            for stave in gongan[ParserTag.STAVES]:
                del stave[ParserTag.STAVES]  # remove superfluous key
                # Parse the beats into Note objects
                stave[ParserTag.BEATS] = [
                    self._parse_stave(beat, stave[ParserTag.POSITION]) for beat in stave[ParserTag.BEATS]
                ]
            # Transpose the gongan from stave-oriented to beat-oriented
            gongan[ParserTag.BEATS] = self._staves_to_beats(gongan[ParserTag.STAVES])
            del gongan[ParserTag.STAVES]
        self._update_grace_notes(notation_dict)

        if self.has_errors:
            self.logerror("Program halted.")
            exit()

        notation = Notation(notation_dict=notation_dict, settings=self.run_settings)

        return notation


if __name__ == "__main__":
    settings = get_run_settings()
    parser = NotationTatsuParser(settings)
    notation_dict = parser.parse_notation()
    print(notation_dict)
