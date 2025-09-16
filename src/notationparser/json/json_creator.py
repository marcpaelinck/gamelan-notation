"""This is the module that actually generates the MIDI messages.
It is used by the MidiGenerator (score_to_midi module).
"""

import json
import math
import re
from typing import ClassVar, override

from _ctypes import PyObj_FromPtr
from pydantic import BaseModel

from src.common.classes import Beat
from src.common.constants import Position
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


class NoIndent(object):
    """Value wrapper. See explanation in MyEncoder class def."""

    def __init__(self, value):
        self.value = value


class MyEncoder(json.JSONEncoder):
    """Makes it possible to disable indentation for parts of a serializable structure by wrapping these parts
    with the NoIndent class.
    Note: the encoder only seems to work with json.dumps, not with json.dump.
    See https://stackoverflow.com/questions/13249415/how-to-implement-custom-indentation-when-pretty-printing-with-the-json-module
    """

    FORMAT_SPEC = "@@{}@@"
    regex = re.compile(FORMAT_SPEC.format(r"(\d+)"))

    def __init__(self, **kwargs):
        # Save copy of any keyword argument values needed for use here.
        self.__sort_keys = kwargs.get("sort_keys", None)
        super(MyEncoder, self).__init__(**kwargs)

    @override
    def default(self, o):
        return self.FORMAT_SPEC.format(id(o)) if isinstance(o, NoIndent) else super(MyEncoder, self).default(o)

    @override
    def encode(self, o):
        format_spec = self.FORMAT_SPEC  # Local var to expedite access.
        json_repr = super(MyEncoder, self).encode(o)  # Default JSON.

        # Replace any marked-up object ids in the JSON repr with the
        # value returned from the json.dumps() of the corresponding
        # wrapped Python object.
        for match in self.regex.finditer(json_repr):
            # see https://stackoverflow.com/a/15012814/355230
            id = int(match.group(1))
            no_indent = PyObj_FromPtr(id)
            json_obj_repr = json.dumps(no_indent.value, sort_keys=self.__sort_keys)

            # Replace the matched id string with json formatted representation
            # of the corresponding Python object.
            json_repr = json_repr.replace('"{}"'.format(format_spec.format(id)), json_obj_repr)

        return json_repr


class JsonCreator(dict):
    """
    Converts a Score object to JSON notation.
    """

    def __init__(self, run_settings: RunSettings):
        super().__init__()
        self.run_settings = run_settings
        self.current_beat_id = 0
        self.current_velocity = run_settings.midi.dynamics[run_settings.midi.default_dynamics]
        self.current_bpm = 60
        # Dummy beat info needed for initial silence

    def velocity2db(self, velocity: int) -> float:
        return round(20 * math.log10(velocity / 127), 1)

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
            "tempo": NoIndent((beat_info.start_bpm, beat_info.end_bpm)),
            "volume": NoIndent((self.velocity2db(beat_info.start_velocity), self.velocity2db(beat_info.end_velocity))),
            # "positions": NoIndent(([pos.value for pos in beat_info.positions])),
            "data": [
                NoIndent(
                    {
                        "label": pos,
                        "value": ([note.symbol.replace("-", " ") for note in measure.passes[-1].notes]),
                    }
                )
                for pos, measure in beat.measures.items()
            ],
        }
        self["sections"].append(beat_dict)

    def save_to_json(self):
        """Saves the JSONized score to file. The file is saved in compact form for production."""
        indent = None if self.run_settings.options.notation_to_midi.run_type is RunType.PRODUCTION else 4
        jsonized = json.dumps(self, indent=indent, cls=MyEncoder)
        with open(self.run_settings.json_out_filepath, "w", encoding="UTF-8") as outfile:
            outfile.writelines(jsonized)
