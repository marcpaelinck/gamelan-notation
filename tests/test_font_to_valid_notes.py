from typing import Any

import pytest
from _pytest.monkeypatch import MonkeyPatch

import src.settings.settings
from src.common.constants import InstrumentGroup, Pitch, Position, Stroke
from src.settings.font_to_valid_notes import get_note_records
from src.settings.settings import FontFields, MidiNotesFields, get_run_settings


@pytest.fixture(scope="module")
# Monkeypatch version for module scope.
# Source: https://stackoverflow.com/questions/53963822/python-monkeypatch-setattr-with-pytest-fixture-at-module-scope
def monkeymodule():
    mpatch = MonkeyPatch()
    yield mpatch
    mpatch.undo()


def to_tuple(note_records: list[dict[str, Any]]) -> list[tuple[Any]]:
    # Converts a note record (dict) to a hashable value te enable
    # quick searching for a note in a list of valid notes.
    fields = (
        "position",
        MidiNotesFields.PITCH,
        MidiNotesFields.OCTAVE,
        MidiNotesFields.STROKE,
        FontFields.DURATION,
        FontFields.REST_AFTER,
    )
    return [tuple([note[field] for field in fields]) for note in note_records]


@pytest.fixture(scope="module")
def valid_notes(monkeymodule) -> tuple[list[dict[str, Any]]]:
    # Creates a list of valid notes for Semar Pagulingan and for Gong Kebyar
    monkeymodule.setattr(src.settings.settings, "SETTINGSFOLDER", "./tests/settings")
    settings = get_run_settings({"piece": "sinomladrang-sp", "part": "full"})
    notes_sp = get_note_records(settings)
    settings = get_run_settings({"piece": "sinomladrang-gk", "part": "full"})
    notes_gk = get_note_records(settings)
    return to_tuple(notes_sp), to_tuple(notes_gk)


# Combinations that will be tested
TRY_COMBINATIONS = [
    tuple([position, pitch, octave, stroke, duration, rest_after])
    for position in (Position.PEMADE_POLOS, Position.JEGOGAN, Position.REYONG_1)
    for pitch in [Pitch.DING, Pitch.DAING, Pitch.STRIKE, Pitch.DAG, Pitch.DENGDING]
    for octave in (1, 2)
    for stroke in [Stroke.OPEN, Stroke.MUTED, Stroke.TREMOLO, Stroke.GRACE_NOTE, Stroke.TICK1]
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
            [(Stroke.TICK1, Stroke.TICK2), (None,)],
        ),
    },
}
# fmt: on


@pytest.mark.parametrize("combination", TRY_COMBINATIONS)
def test_valid_notes_pokok(combination, valid_notes):
    position = combination[0]
    for instrumentgroup, validnotes in [
        (InstrumentGroup.SEMAR_PAGULINGAN, valid_notes[0]),
        (InstrumentGroup.GONG_KEBYAR, valid_notes[1]),
    ]:
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


def print_test_data(data: tuple[Any], combinations: list[int]):
    for nr, value in enumerate(data):
        if nr in combinations:
            print(f"{nr}: {value}")


if __name__ == "__main__":
    print_test_data(TRY_COMBINATIONS, [300, 301, 302])
