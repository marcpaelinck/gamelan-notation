"""Separate location for lookup tables, which are populated with methods in utils.py.
    This construct enables to avoid circular references when importing the variables.
"""

from src.common.classes import InstrumentTag, MidiNote, Note, Preset
from src.common.constants import (
    InstrumentPosition,
    InstrumentType,
    Octave,
    Pitch,
    Stroke,
)

SYMBOL_TO_NOTE_LOOKUP: dict[str, Note] = dict()
NOTE_LIST: list[Note] = list()
SYMBOLVALUE_TO_MIDINOTE_LOOKUP: dict[tuple[InstrumentPosition, Pitch, Octave, Stroke], MidiNote] = dict()
PRESET_LOOKUP: dict[InstrumentType, Preset] = dict()
TAG_TO_POSITION_LOOKUP: dict[InstrumentTag, list[InstrumentPosition]] = dict()
POSITION_TO_RANGE_LOOKUP: dict[InstrumentPosition, tuple[Pitch, Octave, Stroke]] = dict()


def get_bank_mido(instrument: InstrumentType):
    # returns the bank number with offset 0 (Python type)
    return PRESET_LOOKUP[instrument].bank - 1


def get_preset_mido(instrument: InstrumentType):
    # returns the preset number with offset 0 (Python type)
    return PRESET_LOOKUP[instrument].preset - 1


def get_channel_mido(instrument: InstrumentType):
    # returns the channel number with offset 0 (Python type)
    return PRESET_LOOKUP[instrument].channel - 1
