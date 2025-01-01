import pytest
from mido import Message

from src.common.classes import Note
from src.common.constants import InstrumentType, Position, Stroke
from src.notation2midi.midi_track import MidiTrackX
from src.settings.classes import RunSettings


@pytest.fixture
def midi_track():
    position = Position("Test Position")
    preset = Preset(channel=1, port=0, bank=0, preset=0)
    run_settings = RunSettings()
    return MidiTrackX(position, preset, run_settings)


def test_process_grace_note_with_rest(midi_track):
    midi_track.time_since_last_note_end = 100
    midi_duration = midi_track._process_grace_note()
    assert midi_duration == min(50, int(0.5 * BASE_NOTE_TIME))
    assert midi_track.time_since_last_note_end == 50


def test_process_grace_note_with_note_duration(midi_track):
    midi_track.time_since_last_note_end = 0
    midi_track.last_note = Note(duration=2, pitch=60, stroke=Stroke.NORMAL)
    midi_track.last_noteoff_msg = Message("note_off", note=60, time=100)
    midi_duration = midi_track._process_grace_note()
    assert midi_duration == int(2 * BASE_NOTE_TIME / 2)
    assert midi_track.last_noteoff_msg.time == 100 - midi_duration


def test_process_grace_note_with_no_previous_note_or_rest(midi_track):
    midi_track.time_since_last_note_end = 0
    midi_track.last_note = None
    midi_track.last_noteoff_msg = Message("note_off", note=60, time=100)
    midi_duration = midi_track._process_grace_note()
    assert midi_duration == int(0.5 * BASE_NOTE_TIME)
    assert midi_track.last_noteoff_msg.time == 100 - midi_duration
