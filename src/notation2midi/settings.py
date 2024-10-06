import os
from enum import StrEnum
from typing import Any

import yaml
from pydantic import BaseModel

from src.common.classes import RunSettings
from src.common.constants import NotationFont

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
    GROUP = "groups"


# instrumenttags.tsv
class InstrumentTagFields(SStrEnum):
    TAG = "tag"
    INFILE = "infile"
    POSITION = "positions"


# midinotes.tsv
class MidiNotesFields(SStrEnum):
    INSTRUMENTGROUP = "instrumentgroup"
    INSTRUMENTTYPE = "instrumenttype"
    POSITIONS = "positions"
    PITCH = "pitch"
    OCTAVE = "octave"
    STROKE = "stroke"
    REMARK = "remark"
    SAMPLE = "sample"
    PRESET = "preset"


class PresetsFields(SStrEnum):
    INSTRUMENTGROUP = "instrumentgroup"
    INSTRUMENTTYPE = "instrumenttype"
    BANK = "bank"
    PRESET = "preset"
    PRESET_NAME = "preset_name"


SETTINGSFOLDER = "./settings"
RUN_SETTINGSFILE = "run-settings.yaml"
DATA_INFOFILE = "data.yaml"


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


def get_run_settings() -> RunSettings:
    """Retrieves the run settings from the run settings yaml file, enriched with information
       from the data information yaml file.

    Returns:
        RunSettings: settings object
    """
    run_settings_dict = read_settings(RUN_SETTINGSFILE)
    data_dict = read_settings(DATA_INFOFILE)

    settings_dict = dict()

    composition = data_dict["notation"]["compositions"][run_settings_dict["composition"]]
    settings_dict["notation"] = get_settings_fields(
        RunSettings.Notation, run_settings_dict | data_dict["notation"] | composition
    )

    settings_dict["midi"] = get_settings_fields(
        RunSettings.MidiInfo, run_settings_dict | run_settings_dict["midi"] | data_dict["midi_definitions"]
    )

    settings_dict["instruments"] = get_settings_fields(
        RunSettings.InstrumentInfo, run_settings_dict | data_dict["instrument_info"] | composition
    )

    settings_dict["font"] = get_settings_fields(
        RunSettings.FontInfo,
        run_settings_dict
        | data_dict["font_definitions"]
        | composition
        | data_dict["font_definitions"]["font_files"][composition["font_version"]],
    )

    settings_dict["switches"] = get_settings_fields(RunSettings.Switches, run_settings_dict)

    return RunSettings.model_validate(settings_dict)


if __name__ == "__main__":
    settings = get_run_settings()
    print(settings)
