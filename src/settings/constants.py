from enum import StrEnum

from pydantic_core import core_schema

# Names of the environment variables in the .env and .env.test files
ENV_VAR_CONFIG_PATH = "GAMELAN_NOTATION_CONFIG_PATH"
ENV_VAR_NOTATIONS_PATH = "GAMELAN_NOTATION_NOTATIONDOCS_PATH"
ENV_VAR_N2M_SETTINGS_PATH = "GAMELAN_NOTATION_N2M_SETTINGS_PATH"
ENV_VAR_SETTINGS_DATA_FOLDER = "GAMELAN_NOTATION_SETTINGS_DATA_FOLDER"


class SStrEnum(StrEnum):
    """Base class for enums, with modified str value"""

    def __str__(self):
        return self.value

    @classmethod
    def __get_pydantic_core_schema__(cls, source_type, handler):
        # Create a schema that checks for valid names or values
        return core_schema.union_schema(
            [
                # First, check if the input is a valid enum member
                core_schema.is_instance_schema(cls),
                # If not, check if it matches a name or value
                core_schema.chain_schema(
                    [
                        core_schema.literal_schema([m.name for m in cls] + [m.value for m in cls]),
                        core_schema.no_info_plain_validator_function(
                            lambda x: cls[x] if x in cls.__members__ else cls(x)
                        ),
                    ]
                ),
            ]
        )


# Enums containing field names of the configuration data tables in subfolders of the settings folder.


class PresetsFields(SStrEnum):
    """config/midi/presets.tsv"""

    INSTRUMENTGROUP = "instrumentgroup"
    INSTRUMENTTYPE = "instrumenttype"
    POSITION = "position"
    BANK = "bank"
    PRESET = "preset"
    CHANNEL = "channel"
    MIDIOFFSET = "midioffset"
    PRESET_NAME = "preset_name"


class MidiNotesFields(SStrEnum):
    """config/midi/gamelan_midinotes<nr>.tsv"""

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
    """config/font/balimusic<nr>font.tsv"""

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
    """config/instruments/instruments.tsv"""

    GROUP = "group"
    INSTRUMENTTYPE = "instrumenttype"
    INSTRUMENT = "instrument"
    POSITION = "position"
    TONES = "tones"
    EXTENDED_TONES = "extended_tones"
    STROKES = "strokes"
    PATTERNS = "patterns"
    RESTS = "rests"


class InstrumentTagFields(SStrEnum):
    """config/instruments/instrumenttags.tsv"""

    TAG = "tag"
    ADDITION = "addition"
    GROUPS = "groups"
    INFILE = "infile"
    POSITIONS = "positions"


class RuleFields(SStrEnum):
    """config/instruments/rules.tsv"""

    GROUP = "group"
    RULETYPE = "ruletype"
    POSITIONS = "positions"
    PARAMETER1 = "parameter1"
    VALUE1 = "value1"
    PARAMETER2 = "parameter2"
    VALUE2 = "value2"


class Yaml(SStrEnum):
    """YAML fieldnames and (enum) values"""

    NOTATIONFILES = "notationfiles"
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
