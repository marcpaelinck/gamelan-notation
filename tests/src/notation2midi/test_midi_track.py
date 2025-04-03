import os
import unittest

from mido import Message

from src.common.classes import Preset
from src.common.constants import Position
from src.notation2midi.midi_track import MidiTrackX
from src.settings.settings import Settings


def setUpModule():
    os.environ["GAMELAN_NOTATION_CONFIG_PATH"] = "./tests/settings/config.yaml"
    os.environ["GAMELAN_NOTATION_N2M_SETTINGS_PATH"] = "./tests/settings/notation2midi.yaml"


class TestSpecialNotes(unittest.TestCase):
    def setUp(self):
        self.run_settings = Settings.get()
        position = Position.PEMADE_POLOS
        preset = Preset.get_preset(position)
        self.midi_track: MidiTrackX = MidiTrackX(position, preset, self.run_settings)

    def test_process_grace_note_with_preceding_rest_or_note(self):
        self.midi_track.current_ticktime = 1000
        self.midi_track.ticktime_last_message = 950
        midi_duration = self.midi_track._grace_note_duration()
        assert midi_duration == min(50, int(0.5 * self.run_settings.midi.base_note_time))

    def test_process_grace_note_with_no_previous_note_or_rest(self):
        self.midi_track.current_ticktime = 0
        self.midi_track.ticktime_last_message = 0
        self.midi_track.last_note = None
        self.midi_track.last_noteoff_msgs = [Message("note_off", note=60, time=100)]
        midi_duration = self.midi_track._grace_note_duration()
        assert midi_duration == 0
