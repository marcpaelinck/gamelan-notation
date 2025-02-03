import pytest
from mido import Message

from src.common.classes import Preset
from src.common.constants import Position
from src.notation2midi.midi_track import MidiTrackX
from src.settings.classes import RunSettings
from src.settings.settings import get_run_settings


@pytest.fixture
def run_settings() -> RunSettings:
    return get_run_settings()


@pytest.fixture
def midi_track(run_settings) -> MidiTrackX:
    position = Position.PEMADE_POLOS
    preset = Preset.get_preset(position)
    return MidiTrackX(position, preset, run_settings)


def test_process_grace_note_with_preceding_rest_or_note(midi_track: MidiTrackX, run_settings: RunSettings):
    midi_track.current_ticktime = 1000
    midi_track.ticktime_last_message = 950
    midi_duration = midi_track._grace_note_duration()
    assert midi_duration == min(50, int(0.5 * run_settings.midi.base_note_time))


def test_process_grace_note_with_no_previous_note_or_rest(midi_track: MidiTrackX, run_settings: RunSettings):
    midi_track.current_ticktime = 0
    midi_track.ticktime_last_message = 0
    midi_track.last_note = None
    midi_track.last_noteoff_msgs = [Message("note_off", note=60, time=100)]
    midi_duration = midi_track._grace_note_duration()
    assert midi_duration == 0
