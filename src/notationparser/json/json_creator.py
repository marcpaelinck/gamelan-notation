"""This is the module that actually generates the MIDI messages.
It is used by the MidiGenerator (score_to_midi module).
"""

import json
from typing import ClassVar

from pydantic import BaseModel

from src.common.classes import Beat
from src.common.logger import Logging
from src.settings.classes import RunSettings, RunType

logger = Logging.get_logger(__name__)


class BeatInfo(BaseModel):
    UPDATEFREQ: ClassVar[int] = 24
    fullid: str
    start_bpm: int
    end_bpm: int
    start_velocity: int
    end_velocity: int
    duration: float


class JsonCreator(dict):
    """
    Converts a Score object to JSON notation and keeps track of the play time.
    """

    def __init__(self, run_settings: RunSettings):
        super().__init__()
        self.run_settings = run_settings
        self.current_beat_id = 0
        self.current_velocity = run_settings.midi.dynamics[run_settings.midi.default_dynamics]
        self.current_bpm = 60
        # Dummy beat info needed for initial silence

    def add_title(self, title: str):
        """Adds a 'title' entry"""
        self["title"] = title

    def add_composer(self, composer: str):
        """Adds a 'composer' entry"""
        self["composer"] = composer

    def append_beat_info(self, beat: Beat, beat_info: BeatInfo):
        """Appends a beat to the JSON structure."""
        if not self.get("sections", None):
            self["sections"] = []

        self.current_beat_id += 1
        beat_dict = {
            "id": self.current_beat_id,
            "title": beat_info.fullid,
            "tempo": beat_info.start_bpm,
            "data": [
                {
                    "label": pos,
                    "value": ([note.symbol.replace("-", " ") for note in measure.passes[-1].notes]),
                }
                for pos, measure in beat.measures.items()
            ],
        }
        self["sections"].append(beat_dict)

    def save_to_json(self):
        """Saves the JSONized score to file. The file is saved in compact form for production."""
        indent = None if self.run_settings.options.notation_to_midi.run_type is RunType.PRODUCTION else 4
        with open(self.run_settings.json_out_filepath, "w", encoding="UTF-8") as outfile:
            json.dump(self, outfile, indent=indent)
