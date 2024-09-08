import os
from enum import StrEnum

import yaml

from src.common.classes import RunSettings
from src.common.constants import NotationFont

BASE_NOTE_TIME = 24
BASE_NOTES_PER_BEAT = 4
ATTENUATION_SECONDS_AFTER_MUSIC_END = 10  # additional time in seconds to let final chord attenuate.
MIDI_NOTES_DEF_FILE = "./settings/midinotes.tsv"
FONT_DEF_FILES = {
    NotationFont.BALIMUSIC4: "./settings/balimusic4font.tsv",
    NotationFont.BALIMUSIC5: "./settings/balimusic5font.tsv",
}
TAGS_DEF_FILE = "./settings/instrumenttags.tsv"
SOUNDFONT_FILE = "./settings/Gong Kebyar MP2.sf2"

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
    CHANNEL = "channel"
    MIDI = "midi"


def get_settings(filename: str) -> dict:
    with open(os.path.join("./settings", filename), "r") as settingsfile:
        return yaml.load(settingsfile, Loader=yaml.SafeLoader)


def get_run_settings():
    run_settings_dict = get_settings("run-settings.yaml")
    notation_settings_dict = get_settings("notation-info.yaml")
    run_settings_dict.update(notation_settings_dict["notationfiles"][run_settings_dict["title"]])
    run_settings_dict["datapath"] = os.path.join(
        notation_settings_dict["notationfolder"], run_settings_dict["subfolder"]
    )
    return RunSettings.model_validate(run_settings_dict)


if __name__ == "__main__":
    settings = get_run_settings()
    print(settings)
