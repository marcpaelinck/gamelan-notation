import copy
import pickle
from collections import ChainMap

from tatsu import compile
from tatsu.model import ParseModel
from tatsu.util import asjson

from src.common.classes import InstrumentTag, NamedIntID, Notation, Note
from src.common.constants import NotationDict, ParserTag, Position, Stroke
from src.common.metadata_classes import MetaData
from src.notation2midi.classes import ParserModel
from src.notation2midi.special_notes_treatment import (
    generate_tremolo,
    get_nearest_note,
    update_grace_notes_octaves,
)
from src.settings.classes import RunSettings
from src.settings.settings import get_run_settings


# The following classes display meaningful names for the IDs
# which will be used as key values in the output dict structure
class PassID(NamedIntID):
    name = "PASS"
    default = "DEFAULT PASS"


class GonganID(NamedIntID):
    name = "GONGAN"
    default = "SCORE LEVEL"


class BeatID(NamedIntID):
    name = "BEAT"
    default = "DEFAULT BEAT"  # should remain unused


class Notation5TatsuParser(ParserModel):
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
            pass_ = PassID(int(stave[ParserTag.POSITION][ParserTag.PASS]))
            stave[ParserTag.POSITION] = positions[0]
            stave[ParserTag.PASS] = pass_
            if len(positions) > 1:
                for position in positions[1:]:
                    newstave = copy.deepcopy(stave)
                    newstave[ParserTag.POSITION] = position
                    newstave[ParserTag.PASS] = pass_
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
                position: {
                    stave[ParserTag.PASS]: (
                        stave[ParserTag.BEATS][beat_seq] if beat_seq < len(stave[ParserTag.BEATS]) else []
                    )
                    for stave in staves
                    if stave[ParserTag.POSITION] == position
                }
                for position in positions
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
            for self.curr_beat_id, staves in beat_dict[ParserTag.BEATS].items():
                # if not isinstance(self.curr_beat_id, int):
                #     continue
                for position, stave in staves.items():
                    for pass_, notes in stave.items():
                        update_grace_notes_octaves(notes=notes, group=self.run_settings.instruments.instrumentgroup)

    def parse_notation(self, notationpath: str | None = None) -> NotationDict:
        if not notationpath:
            notationpath = self.run_settings.notation.filepath
        self.loginfo(f"Parsing file {notationpath}")

        # Parse the notation using the ebnf grammar.
        try:
            self.loginfo(f"Using {self.model_source}.")
            with open(notationpath, "r") as notationfile:
                notation = notationfile.read()
            ast = self.grammar_model.parse(notation)
        except Exception as e:
            print(e)
            return None
        notation_dict = asjson(ast)

        # Convert the gongan structure into a dict {id: gongan}
        # The sum function concatenates the final gongan to the list of gongans (final gongan is defined separately in the grammar)
        notation_dict = {GonganID(-1): notation_dict[ParserTag.UNBOUND]} | {
            GonganID(count + 1): gongan for count, gongan in enumerate(sum(notation_dict[ParserTag.GONGANS][0], []))
        }

        # group items by category: comment, metadata and staves.
        notation_dict = {
            gongan_id: {
                key: [e[key] for e in gongan if key.value in e.keys()]
                for key in [ParserTag.COMMENT, ParserTag.METADATA, ParserTag.STAVES]
            }
            for gongan_id, gongan in notation_dict.items()
        }

        # Flatten the metadata items, create MetaData and Note objects
        for gongan in notation_dict.values():
            # Parse the metadata into MetaData objects
            gongan[ParserTag.METADATA] = [
                MetaData(data=self._flatten_meta(meta)) for meta in gongan[ParserTag.METADATA]
            ]
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

        notation = Notation(notation_dict=notation_dict, settings=self.run_settings)

        return notation


if __name__ == "__main__":
    settings = get_run_settings()
    parser = Notation5TatsuParser(settings)
    notation_dict = parser.parse_notation()
    print(notation_dict)
