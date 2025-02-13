from enum import StrEnum

SETTINGSFOLDER = "./settings"
TEST_SETTINGSFOLDER = "./settings/test"
RUN_SETTINGSFILE = "notation2midi.yaml"
DATA_INFOFILE = "data.yaml"


class SStrEnum(StrEnum):
    def __str__(self):
        return self.value


# gamelan_midinotes<nr>.tsv
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


# balimusic<nr>font.tsv
class FontFields(SStrEnum):
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


# Combination of the above classes
class NoteFields(SStrEnum):
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


# instruments.tsv
class InstrumentFields(SStrEnum):
    GROUP = "group"
    INSTRUMENT = "instrument"
    POSITION = "position"
    POSITION_RANGE = "position_range"
    EXTENDED_POSITION_RANGE = "extended_position_range"


# instrumenttags.tsv
class InstrumentTagFields(SStrEnum):
    TAG = "tag"
    INFILE = "infile"
    POSITIONS = "positions"


# rules.tsv
class RuleFields(SStrEnum):
    GROUP = "group"
    RULETYPE = "ruletype"
    POSITIONS = "positions"
    PARAMETER1 = "parameter1"
    VALUE1 = "value1"
    PARAMETER2 = "parameter2"
    VALUE2 = "value2"


class PresetsFields(SStrEnum):
    INSTRUMENTGROUP = "instrumentgroup"
    INSTRUMENTTYPE = "instrumenttype"
    POSITION = "position"
    BANK = "bank"
    PRESET = "preset"
    CHANNEL = "channel"
    PRESET_NAME = "preset_name"


class Yaml(SStrEnum):

    # YAML fieldnames and (enum) values
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
    OPTIONS = "options"
    NOTATION_TO_MIDI = "notation_to_midi"
    RUNTYPE = "runtype"
    COMPOSITION = "composition"
    PART = "part"
    PART_ID = "part_id"
    INSTRUMENTGROUPS = "instrumentgroups"
    INSTRUMENTGROUP = "instrumentgroup"
    MIDIPLAYER = "midiplayer"
    MULTIPLE_RUNS = "multiple_runs"
    # Enum values
    RUN_SINGLE = "RUN_SINGLE"
    RUN_TEST = "RUN_TEST"
    RUN_ALL = "RUN_ALL"
