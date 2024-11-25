import os
import re
from enum import StrEnum
from typing import Any

import yaml
from pydantic import BaseModel

from src.common.classes import RunSettings
from src.common.logger import get_logger

logger = get_logger(__name__)

BASE_NOTE_TIME = 24
BASE_NOTES_PER_BEAT = 4
ATTENUATION_SECONDS_AFTER_MUSIC_END = 10  # additional time in seconds to let final chord attenuate.

METADATA = "metadata"
COMMENT = "comment"
NON_INSTRUMENT_TAGS = [METADATA, COMMENT]


# list of column headers used in the settings files

# balimusic4font.tsv: Fields should correspond exactly with the Character class attributes


class SStrEnum(StrEnum):
    def __str__(self):
        return self.value


class FontFields(SStrEnum):
    SYMBOL = "symbol"
    UNICODE = "unicode"
    SYMBOL_DESCRIPTION = "symbol_description"
    BALIFONT_SYMBOL_DESCRIPTION = "balifont_symbol_description"
    PITCH = "pitch"
    OCTAVE = "octave"
    STROKE = "stroke"
    DURATION = "duration"
    REST_AFTER = "rest_after"
    DESCRIPTION = "description"


# instruments.tsv
class InstrumentFields(SStrEnum):
    POSITION = "position"
    INSTRUMENT = "instrument"
    GROUP = "group"


# instrumenttags.tsv
class InstrumentTagFields(SStrEnum):
    TAG = "tag"
    INFILE = "infile"
    POSITIONS = "positions"


# midinotes.tsv
class MidiNotesFields(SStrEnum):
    INSTRUMENTGROUP = "instrumentgroup"
    INSTRUMENTTYPE = "instrumenttype"
    POSITIONS = "positions"
    PITCH = "pitch"
    OCTAVE = "octave"
    STROKE = "stroke"
    REMARK = "remark"
    MIDINOTE = "midinote"
    ROOTNOTE = "rootnote"
    SAMPLE = "sample"


class PresetsFields(SStrEnum):
    INSTRUMENTGROUP = "instrumentgroup"
    INSTRUMENTTYPE = "instrumenttype"
    POSITION = "position"
    BANK = "bank"
    PRESET = "preset"
    CHANNEL = "channel"
    PRESET_NAME = "preset_name"


SETTINGSFOLDER = "./settings"
RUN_SETTINGSFILE = "run-settings.yaml"
DATA_INFOFILE = "data.yaml"


def post_process(subdict: dict[str, Any], run_settings_dict: dict[str, Any] = None):
    """This function enables references to yaml key values using ${<yaml_path>} notation.
    The function substitutes these values with the corresponding yaml settings values.
    Does not (yet) implement usage of references within a list structure.

    Args:
        subdict (dict[str, Any]): Part of a yaml stucture in Python format.
        run_settings_dict(dict[str, Any]): Full yaml structure in Python dict format.
    """
    found: re.Match

    for key, value in subdict.items():
        if isinstance(value, dict):
            # Iterate through dict structures until a root node is found
            subdict[key] = post_process(value, run_settings_dict or subdict)
        elif isinstance(value, str):
            # Only implemented for key: str items. Does not operate on list structures (yet)
            while found := re.search(r"\$\{([\w\.]+)\}", value):
                keys = found.group(1).split(".")
                item = run_settings_dict
                for key1 in keys:
                    item = item[key1]
                value = value.replace(found.group(0), item)
                i = 1
            subdict[key] = value
    return subdict


def read_settings(filename: str) -> dict:
    """Retrieves settings from the given (YAML) file. The file should occur in SETTINGSFOLDER.

    Args:
        filename (str): YAML file name.

    Returns:
        dict: dict containing all the settings contained in the file.
    """
    with open(os.path.join(SETTINGSFOLDER, filename), "r") as settingsfile:
        return yaml.load(settingsfile, Loader=yaml.SafeLoader)


def get_settings_fields(cls: BaseModel, settings_dict: dict) -> dict[str, Any]:
    """Retrieves all the fields from run_settings_dict and data_dict that match the field names of cls.

    Args:
        cls (BaseModel): Pydantic class for which to retrieve the fields
        settings_dict (dict): Dict containing settings fields

    Returns:
        dict[str, Any]: _description_
    """
    retval = {key: settings_dict[key] for key in cls.model_fields.keys() if key in settings_dict}
    return retval


def get_run_settings(notation: dict[str, str] = None) -> RunSettings:
    """Retrieves the run settings from the run settings yaml file, enriched with information
       from the data information yaml file.

    Returns:
        RunSettings: settings object
    """
    run_settings_dict = read_settings(RUN_SETTINGSFILE)
    data_dict = read_settings(DATA_INFOFILE)

    # YAML fieldnames
    NOTATION = "notation"
    DEFAULTS = "defaults"
    MIDI = "midi"
    SAMPLES = "samples"
    INSTRUMENTS = "instruments"
    FONT = "font"
    SOUNDFONT = "soundfont"
    OPTIONS = "options"
    COMPOSITION = "composition"
    FILE = "file"
    PART = "part"
    LOOP = "loop"
    FULL = "full"
    INSTRUMENTGROUP = "instrumentgroup"
    MIDIVERSION = "midiversion"
    FONTVERSION = "fontversion"

    if notation:
        run_settings_dict[NOTATION] = notation

    settings_dict = dict()

    composition = data_dict[NOTATION][COMPOSITION][run_settings_dict[NOTATION][COMPOSITION]]
    settings_dict[NOTATION] = get_settings_fields(
        RunSettings.NotationInfo,
        data_dict[NOTATION][COMPOSITION][DEFAULTS] | data_dict[NOTATION] | composition | run_settings_dict[NOTATION],
    )
    settings_dict[NOTATION][FILE] = composition[PART][run_settings_dict[NOTATION][PART]]
    # Only 'full' composition will be extended with 'attenuation time'.
    settings_dict[NOTATION][LOOP] = run_settings_dict[NOTATION][PART] != FULL

    midiversion = data_dict[MIDI][MIDIVERSION][run_settings_dict[MIDI][MIDIVERSION]]
    settings_dict[MIDI] = get_settings_fields(
        RunSettings.MidiInfo, data_dict[MIDI] | run_settings_dict[MIDI] | midiversion
    )

    samples = data_dict[SAMPLES][INSTRUMENTGROUP][run_settings_dict[SAMPLES][INSTRUMENTGROUP]]
    settings_dict[SAMPLES] = get_settings_fields(
        RunSettings.SampleInfo, samples | run_settings_dict[SAMPLES] | data_dict[SAMPLES]
    )

    instruments = data_dict[INSTRUMENTS][INSTRUMENTGROUP][composition[INSTRUMENTGROUP]]
    settings_dict[INSTRUMENTS] = get_settings_fields(
        RunSettings.InstrumentInfo,
        data_dict[INSTRUMENTS]
        | data_dict[NOTATION][COMPOSITION][run_settings_dict[NOTATION][COMPOSITION]]
        | instruments,
    )

    font = data_dict[FONT][FONTVERSION][composition[FONTVERSION]] | {FONTVERSION: composition[FONTVERSION]}
    settings_dict[FONT] = get_settings_fields(RunSettings.FontInfo, data_dict[FONT] | font)

    settings_dict[SOUNDFONT] = get_settings_fields(
        RunSettings.SoundfontInfo, data_dict[SOUNDFONT] | run_settings_dict[SOUNDFONT]
    )

    settings_dict[OPTIONS] = get_settings_fields(RunSettings.Options, run_settings_dict[OPTIONS])

    settings_dict = post_process(settings_dict)

    return RunSettings.model_validate(settings_dict)


if __name__ == "__main__":
    # For testing
    settings = get_run_settings()
    print(settings.soundfont)
    print(settings.soundfont.sf_filepath_list)
