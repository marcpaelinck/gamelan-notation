from collections import defaultdict
from typing import Any

from src.common.constants import InstrumentGroup, PatternType, Pitch, Position, Stroke
from src.settings.constants import NoteFields
from src.settings.font_to_valid_notes import ValidNoteGenerator
from src.settings.settings import Settings
from tests.conftest import BaseUnitTestCase

FIELDS_IN_TUPLE = (
    NoteFields.POSITION,
    NoteFields.PITCH,
    NoteFields.OCTAVE,
    NoteFields.EFFECT,
    NoteFields.NOTE_VALUE,
)


class SettingsTester(BaseUnitTestCase):

    def to_tuple(self, note_records: list[dict[str, Any]]) -> list[tuple[Any]]:
        # Create a tuple containing the note fields that we want to test.
        return [tuple([note[field] for field in FIELDS_IN_TUPLE]) for note in note_records]

    def valid_notes_sp(
        self,
    ) -> list[dict[str, Any]]:
        # Creates a list of valid notes for Semar Pagulingan
        settings = Settings.get(notation_id="test-semarpagulingan", part_id="full")
        notes_sp = ValidNoteGenerator(settings).get_note_records()
        return [{field.value: note[field] for field in FIELDS_IN_TUPLE} for note in notes_sp]

    def valid_notes_gk(
        self,
    ) -> list[dict[str, Any]]:
        # Creates a list of valid notes for  Gong Kebyar
        settings = Settings.get(notation_id="test-gongkebyar", part_id="full")
        notes_gk = ValidNoteGenerator(settings).get_note_records()
        return [{field.value: note[field] for field in FIELDS_IN_TUPLE} for note in notes_gk]

    # Combinations that will be tested
    def setUp(self):
        self.TRY_COMBINATIONS = [
            {
                NoteFields.POSITION.value: position,
                NoteFields.PITCH.value: pitch,
                NoteFields.OCTAVE.value: octave,
                NoteFields.EFFECT.value: effect,
                NoteFields.NOTE_VALUE.value: note_value,
            }
            for position in (Position.PEMADE_POLOS, Position.JEGOGAN, Position.REYONG_1)
            for pitch in [Pitch.DING, Pitch.DAING, Pitch.STRIKE, Pitch.DAG, Pitch.DENGDING]
            for octave in (1, 2)
            for effect in [Stroke.OPEN, Stroke.MUTED, PatternType.TREMOLO, Stroke.GRACE_NOTE]
            for note_value in (0, 0.25, 1.0)
        ]
        # fmt: off
        self.VALID_PITCH_OCTAVE = {
            InstrumentGroup.SEMAR_PAGULINGAN: {
                Position.PEMADE_POLOS: [(Pitch.DING, 1), (Pitch.DONG, 1), (Pitch.DENG, 1), (Pitch.DEUNG, 1), (Pitch.DUNG, 1), (Pitch.DANG, 1), (Pitch.DAING, 1)],
                Position.JEGOGAN: [(Pitch.DING, 1), (Pitch.DONG, 1), (Pitch.DENG, 1), (Pitch.DEUNG, 1), (Pitch.DUNG, 1), (Pitch.DANG, 1), (Pitch.DAING, 1)],
                Position.REYONG_1: [],
            },
            InstrumentGroup.GONG_KEBYAR: {
                Position.PEMADE_POLOS: [ (Pitch.DONG, 0), (Pitch.DENG, 0), (Pitch.DUNG, 0), (Pitch.DANG, 0), (Pitch.DING, 1), (Pitch.DONG, 1),  
                                        (Pitch.DENG, 1), (Pitch.DUNG, 1), (Pitch.DANG, 1), (Pitch.DING, 2)],
                Position.JEGOGAN: [(Pitch.DING, 1), (Pitch.DONG, 1), (Pitch.DENG, 1), (Pitch.DUNG, 1), (Pitch.DANG, 1)],
                Position.REYONG_1: [(Pitch.DENG, 0), (Pitch.DUNG, 0), (Pitch.DANG, 0), (Pitch.DING, 1), (Pitch.DONG, 1), (Pitch.DENGDING, 0), (Pitch.STRIKE, None),
                                    (Pitch.BYONG, None)],
            },
        }
        self.VALID_STROKE_DURATION = {
            InstrumentGroup.SEMAR_PAGULINGAN: {
                Position.PEMADE_POLOS: [(Stroke.OPEN, 0.25), (Stroke.OPEN, 0.5), (Stroke.OPEN, 1.0), (Stroke.ABBREVIATED, 0.25), (Stroke.ABBREVIATED, 0.5), 
                                        (Stroke.ABBREVIATED, 1.0), (Stroke.MUTED, 0.25), (Stroke.MUTED, 0.5), (Stroke.MUTED, 1.0), (PatternType.TREMOLO, 1.0), 
                                        (PatternType.TREMOLO_ACCELERATING, 1.0), (PatternType.NOROT, 1.0), (Stroke.GRACE_NOTE, 0.0)],
                Position.JEGOGAN: [(Stroke.OPEN, 0.25), (Stroke.OPEN, 0.5), (Stroke.OPEN, 1.0), (Stroke.ABBREVIATED, 0.25), (Stroke.ABBREVIATED, 0.5), 
                                   (Stroke.ABBREVIATED, 1.0), (Stroke.MUTED, 0.25), (Stroke.MUTED, 0.5), (Stroke.MUTED, 1.0), (PatternType.TREMOLO, 1.0), 
                                   (PatternType.TREMOLO_ACCELERATING, 1.0)],
                Position.REYONG_1: [],
            },
            InstrumentGroup.GONG_KEBYAR: {
                Position.PEMADE_POLOS: [(Stroke.OPEN, 0.25), (Stroke.OPEN, 0.5), (Stroke.OPEN, 1.0), (Stroke.ABBREVIATED, 0.25), (Stroke.ABBREVIATED, 0.5), 
                                        (Stroke.ABBREVIATED, 1.0), (Stroke.MUTED, 0.25), (Stroke.MUTED, 0.5), (Stroke.MUTED, 1.0), (PatternType.TREMOLO, 1.0), 
                                        (PatternType.TREMOLO_ACCELERATING, 1.0), (PatternType.NOROT, 1.0), (Stroke.GRACE_NOTE, 0.0)],
                Position.JEGOGAN: [(Stroke.OPEN, 0.25), (Stroke.OPEN, 0.5), (Stroke.OPEN, 1.0), (Stroke.ABBREVIATED, 0.25), (Stroke.ABBREVIATED, 0.5), 
                                   (Stroke.ABBREVIATED, 1.0), (Stroke.MUTED, 0.25), (Stroke.MUTED, 0.5), (Stroke.MUTED, 1.0), (PatternType.TREMOLO, 1.0), 
                                   (PatternType.TREMOLO_ACCELERATING, 1.0)],
                Position.REYONG_1: [(Stroke.OPEN, 0.25), (Stroke.OPEN, 0.5), (Stroke.OPEN, 1.0), (Stroke.ABBREVIATED, 0.25), (Stroke.ABBREVIATED, 0.5), 
                                    (Stroke.ABBREVIATED, 1.0), (Stroke.MUTED, 0.25), (Stroke.MUTED, 0.5), (Stroke.MUTED, 1.0), (PatternType.TREMOLO, 1.0), 
                                    (PatternType.TREMOLO_ACCELERATING, 1.0), (Stroke.GRACE_NOTE, 0.0)],
            },
        }

    # fmt: on

    def test_create_note_records(self):
        """Validates the create_note_records function, which returns all valid note feature combinations.
        TRY_COMBINATIONS contains valid and invalid combinations of pitch, octave, stroke and duration.
        We test that only combinations that match VALID_PITCH_OCTAVE and VALID_STROKE_DURATION
        occur in validnotes, the return value of create_note_records."""
        for instrumentgroup, validnotes in [
            (InstrumentGroup.SEMAR_PAGULINGAN, self.valid_notes_sp()),
            (InstrumentGroup.GONG_KEBYAR, self.valid_notes_gk()),
        ]:
            for combination in self.TRY_COMBINATIONS:
                position = combination[NoteFields.POSITION]
                valid_PO = self.VALID_PITCH_OCTAVE.get(instrumentgroup, {}).get(position, None)
                valid_SD = self.VALID_STROKE_DURATION.get(instrumentgroup, {}).get(position, None)
                if (
                    (valid_PO and valid_SD)
                    and (combination[NoteFields.PITCH], combination[NoteFields.OCTAVE]) in valid_PO
                    and (combination[NoteFields.EFFECT], combination[NoteFields.NOTE_VALUE]) in valid_SD
                ):
                    self.assertIn(combination, validnotes)
                else:
                    self.assertNotIn(combination, validnotes)

    def test_unique_features(self):
        for notelist in (self.valid_notes_sp(), self.valid_notes_gk()):
            # Create a dict with the values FIELDS_IN_TUPLE as keys
            # and check that all entries contain exactly one note record.
            notedict = defaultdict(list)
            for note in notelist:
                notedict[tuple([note[field] for field in FIELDS_IN_TUPLE])].append(note)
            for key in notedict.keys():
                assert len(notedict[key]) == 1

    def print_test_data(self, combinations: list[int]):
        for nr, value in enumerate(self.TRY_COMBINATIONS):
            if nr in combinations:
                print(f"{nr}: {value}")
