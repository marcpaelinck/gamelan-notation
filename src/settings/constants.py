from enum import StrEnum

# Names of the environment variables in the .env and .env.test files
ENV_VAR_CONFIG_PATH = "GAMELAN_NOTATION_CONFIG_PATH"
ENV_VAR_N2M_SETTINGS_PATH = "GAMELAN_NOTATION_N2M_SETTINGS_PATH"
ENV_VAR_SETTINGS_DATA_FOLDER = "GAMELAN_NOTATION_SETTINGS_DATA_FOLDER"


class SStrEnum(StrEnum):
    """Base class for enums, with modified str value"""

    def __str__(self):
        return self.value


# Enums containing field names of the configuration data tables in subfolders of the settings folder.


class PresetsFields(SStrEnum):
    """settings/midi/presets.tsv"""

    INSTRUMENTGROUP = "instrumentgroup"
    INSTRUMENTTYPE = "instrumenttype"
    POSITION = "position"
    BANK = "bank"
    PRESET = "preset"
    CHANNEL = "channel"
    PRESET_NAME = "preset_name"


class MidiNotesFields(SStrEnum):
    """settings/midi/gamelan_midinotes<nr>.tsv"""

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


class FontFields(SStrEnum):
    """settings/font/balimusic<nr>font.tsv"""

    SYMBOL = "symbol"
    UNICODE = "unicode"
    SYMBOL_DESCRIPTION = "symbol_description"
    BALIFONT_SYMBOL_DESCRIPTION = "balifont_symbol_description"
    PITCH = "pitch"
    OCTAVE = "octave"
    STROKE = "stroke"
    MODIFIER = "modifier"
    DURATION = "duration"
    REST_AFTER = "rest_after"
    DESCRIPTION = "description"


class NoteFields(SStrEnum):
    """Combination of the above two classes"""

    INSTRUMENTGROUP = "instrumentgroup"
    INSTRUMENTTYPE = "instrumenttype"
    POSITION = "position"
    SYMBOL = "symbol"
    PITCH = "pitch"
    OCTAVE = "octave"
    STROKE = "stroke"
    MODIFIER = "modifier"
    DURATION = "duration"
    REST_AFTER = "rest_after"
    MIDINOTE = "midinote"
    ROOTNOTE = "rootnote"
    SAMPLE = "sample"


class InstrumentFields(SStrEnum):
    """settings/instruments/instruments.tsv"""

    GROUP = "group"
    INSTRUMENT = "instrument"
    POSITION = "position"
    POSITION_RANGE = "position_range"
    EXTENDED_POSITION_RANGE = "extended_position_range"


class InstrumentTagFields(SStrEnum):
    """settings/instruments/instrumenttags.tsv"""

    TAG = "tag"
    ADDITION = "addition"
    GROUPS = "groups"
    INFILE = "infile"
    POSITIONS = "positions"


class RuleFields(SStrEnum):
    """settings/instruments/rules.tsv"""

    GROUP = "group"
    RULETYPE = "ruletype"
    POSITIONS = "positions"
    PARAMETER1 = "parameter1"
    VALUE1 = "value1"
    PARAMETER2 = "parameter2"
    VALUE2 = "value2"


class Yaml(SStrEnum):
    """YAML fieldnames and (enum) values"""

    NOTATIONS = "notations"
    NOTATION = "notation"
    DATA = "data"
    DEFAULTS = "defaults"
    MIDI = "midi"
    MIDIVERSIONS = "midiversions"
    MIDIVERSION = "midiversion"
    SAMPLES = "samples"
    INSTRUMENTS = "instruments"
    FONTS = "fonts"
    FONT = "font"
    FONTVERSIONS = "fontversions"
    FONTVERSION = "fontversion"
    GRAMMARS = "grammars"
    SOUNDFONTS = "soundfonts"
    SOUNDFONT = "soundfont"
    PDF_CONVERTER = "pdf_converter"
    OPTIONS = "options"
    NOTATION_TO_MIDI = "notation_to_midi"
    RUNTYPE = "runtype"
    COMPOSITION = "composition"
    NOTATION_ID = "notation_id"
    PART_ID = "part_id"
    INSTRUMENTGROUPS = "instrumentgroups"
    INSTRUMENTGROUP = "instrumentgroup"
    MIDIPLAYER = "midiplayer"
    MULTIPLE_RUNS = "multiple_runs"
    CONFIGDATA = "configdata"
