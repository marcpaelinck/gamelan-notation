from enum import StrEnum

SETTINGSFOLDER = "./settings"
RUN_SETTINGSFILE = "run-settings.yaml"
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
    POSITION = "position"
    INSTRUMENT = "instrument"
    GROUP = "group"


# instrumenttags.tsv
class InstrumentTagFields(SStrEnum):
    TAG = "tag"
    INFILE = "infile"
    POSITIONS = "positions"


class PresetsFields(SStrEnum):
    INSTRUMENTGROUP = "instrumentgroup"
    INSTRUMENTTYPE = "instrumenttype"
    POSITION = "position"
    BANK = "bank"
    PRESET = "preset"
    CHANNEL = "channel"
    PRESET_NAME = "preset_name"


class Yaml(SStrEnum):

    # YAML fieldnames
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
    SOUNDFONTS = "soundfonts"
    SOUNDFONT = "soundfont"
    OPTIONS = "options"
    COMPOSITION = "composition"
    PART = "part"
    INSTRUMENTGROUPS = "instrumentgroups"
    INSTRUMENTGROUP = "instrumentgroup"
    MIDIPLAYER = "midiplayer"
