from collections import defaultdict
from typing import Any

import pytest
from _pytest.monkeypatch import MonkeyPatch

import src.settings.settings
from src.common.constants import InstrumentGroup, NoteRecord, Pitch, Position, Stroke
from src.settings.constants import NoteFields
from src.settings.font_to_valid_notes import get_note_records
from src.settings.settings import RUN_SETTINGS, get_run_settings


@pytest.fixture(scope="module")
# Monkeypatch version for module scope.
# Source: https://stackoverflow.com/questions/53963822/python-monkeypatch-setattr-with-pytest-fixture-at-module-scope
def monkeymodule():
    mpatch = MonkeyPatch()
    yield mpatch
    mpatch.undo()


FIELDS_IN_TUPLE = (
    NoteFields.POSITION,
    NoteFields.PITCH,
    NoteFields.OCTAVE,
    NoteFields.STROKE,
    NoteFields.DURATION,
    NoteFields.REST_AFTER,
)


def to_tuple(note_records: list[dict[str, Any]]) -> list[tuple[Any]]:
    # Create a tuple containing the note fields that we want to test.
    return [tuple([note[field] for field in FIELDS_IN_TUPLE]) for note in note_records]


@pytest.fixture(scope="module")
def valid_notes(monkeymodule) -> tuple[list[NoteRecord]]:
    # Creates a list of valid notes for Semar Pagulingan and for Gong Kebyar
    monkeymodule.setattr(src.settings.settings, "SETTINGSFOLDER", "./tests/settings")
    settings = get_run_settings({"piece": "sinomladrang-sp", "part": "full"})
    notes_sp = get_note_records(settings)
    settings = get_run_settings({"piece": "sinomladrang-gk", "part": "full"})
    notes_gk = get_note_records(settings)
    return notes_sp, notes_gk


# Combinations that will be tested
TRY_COMBINATIONS = [
    tuple([position, pitch, octave, stroke, duration, rest_after])
    for position in (Position.PEMADE_POLOS, Position.JEGOGAN, Position.REYONG_1)
    for pitch in [Pitch.DING, Pitch.DAING, Pitch.STRIKE, Pitch.DAG, Pitch.DENGDING]
    for octave in (1, 2)
    for stroke in [Stroke.OPEN, Stroke.MUTED, Stroke.TREMOLO, Stroke.GRACE_NOTE]
    for duration in (0.25, 1.0)
    for rest_after in (0,)
]

# Valid combinations of pitch and octave
# fmt: off
VALID_PITCH_OCTAVE = {
    InstrumentGroup.SEMAR_PAGULINGAN: {
        Position.PEMADE_POLOS: (
            [(Pitch.DING, Pitch.DONG, Pitch.DENG, Pitch.DEUNG, Pitch.DUNG, Pitch.DANG, Pitch.DAING), (1,)],
        ),
        Position.JEGOGAN: (
            [(Pitch.DING, Pitch.DONG, Pitch.DENG, Pitch.DEUNG, Pitch.DUNG, Pitch.DANG, Pitch.DAING), (1,)],
        ),
        Position.REYONG_1: None,
    },
    InstrumentGroup.GONG_KEBYAR: {
        Position.PEMADE_POLOS: [((Pitch.DING,), (1, 2)), 
                                ((Pitch.DONG, Pitch.DENG, Pitch.DUNG, Pitch.DANG), (0, 1))],
        Position.JEGOGAN: [((Pitch.DING, Pitch.DONG, Pitch.DENG, Pitch.DUNG, Pitch.DANG), (1,))],
        Position.REYONG_1: [((Pitch.DENG, Pitch.DUNG, Pitch.DANG, Pitch.DENGDING, Pitch.STRIKE), (0,)), 
                            ((Pitch.DING, Pitch.DONG,), (1,)),
                            ((Pitch.STRIKE,), (None,)),],
    },
}

# Valid combinations of stroke and duration
VALID_STROKE_DURATION = {
    InstrumentGroup.SEMAR_PAGULINGAN: {
        Position.PEMADE_POLOS: (
            [(Stroke.OPEN, Stroke.ABBREVIATED, Stroke.MUTED), (0.25, 0.5, 1.0)],
            [(Stroke.TREMOLO, Stroke.TREMOLO_ACCELERATING, Stroke.NOROT), (1.0,)],
            [(Stroke.GRACE_NOTE,), (0.0,)],
        ),
        Position.JEGOGAN: (
            [(Stroke.OPEN, Stroke.ABBREVIATED, Stroke.MUTED), (0.25, 0.5, 1.0)],
            # See remark in font_to_valid_notes.py where tremolo notes are created.
            [(Stroke.TREMOLO, Stroke.TREMOLO_ACCELERATING), (1.0,)],
        ),
        Position.REYONG_1:None,
    },
    InstrumentGroup.GONG_KEBYAR: {
        Position.PEMADE_POLOS: (
            [(Stroke.OPEN, Stroke.ABBREVIATED, Stroke.MUTED), (0.25, 0.5, 1.0)],
            [(Stroke.TREMOLO, Stroke.TREMOLO_ACCELERATING, Stroke.NOROT), (1.0,)],
            [(Stroke.GRACE_NOTE,), (0.0,)],
        ),
        Position.JEGOGAN: (
            [(Stroke.OPEN, Stroke.ABBREVIATED, Stroke.MUTED), (0.25, 0.5, 1.0)],
            # See remark in font_to_valid_notes.py where tremolo notes are created.
            [(Stroke.TREMOLO, Stroke.TREMOLO_ACCELERATING), (1.0,)],
        ),
        Position.REYONG_1: (
            [(Stroke.OPEN, Stroke.ABBREVIATED, Stroke.MUTED), (0.25, 0.5, 1.0)],
            [(Stroke.TREMOLO, Stroke.TREMOLO_ACCELERATING), (1.0,)],
            [(Stroke.GRACE_NOTE,), (0.0, None)],
        ),
    },
}
# fmt: on


@pytest.mark.parametrize("combination", TRY_COMBINATIONS)
def test_valid_notes(combination, valid_notes):
    position = combination[0]
    for instrumentgroup, valid_group_notes in [
        (InstrumentGroup.SEMAR_PAGULINGAN, valid_notes[0]),
        (InstrumentGroup.GONG_KEBYAR, valid_notes[1]),
    ]:
        validnotes = to_tuple(valid_group_notes)
        if (
            VALID_PITCH_OCTAVE[instrumentgroup][position]
            and VALID_STROKE_DURATION[instrumentgroup][position]
            and any(
                combi
                for combi in VALID_PITCH_OCTAVE[instrumentgroup][position]
                if combination[1] in combi[0] and combination[2] in combi[1]
            )
            and any(
                combi
                for combi in VALID_STROKE_DURATION[instrumentgroup][position]
                if combination[3] in combi[0] and combination[4] in combi[1]
            )
        ):
            assert combination in validnotes
        else:
            assert combination not in validnotes


def test_unique_features(valid_notes):
    for notelist in valid_notes:
        # Create a dict with the values FIELDS_IN_TUPLE as keys
        # and check that all entries contain exactly one note record.
        notedict = defaultdict(list)
        for note in notelist:
            notedict[tuple([note[field] for field in FIELDS_IN_TUPLE])].append(note)
        for key in notedict.keys():
            assert len(notedict[key]) == 1


def print_test_data(data: tuple[Any], combinations: list[int]):
    for nr, value in enumerate(data):
        if nr in combinations:
            print(f"{nr}: {value}")


if __name__ == "__main__":
    # Use to determine which test failed
    print_test_data(TRY_COMBINATIONS, [300, 301, 302])
