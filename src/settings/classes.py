import os
import re
from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum
from typing import Any

import numpy as np
import pandas as pd
import yaml
from pydantic import BaseModel, Field

from src.common.constants import (
    AnimationProfiles,
    AnimationStroke,
    Duration,
    DynamicLevel,
    InstrumentGroup,
    InstrumentType,
    MIDIvalue,
    MidiVersion,
    Modifier,
    NotationFontVersion,
    NoteOct,
    Octave,
    Pitch,
    Position,
    RuleParameter,
    RuleType,
    RuleValue,
    Stroke,
)
from src.common.logger import Logging
from src.settings.constants import ENV_VAR_CONFIG_PATH, ENV_VAR_N2M_SETTINGS_PATH, Yaml

logger = Logging.get_logger(__name__)

# DATA contains information about the location of the settings data tables and how to format their contents.
# Its structure enables to process each settings data table with the same generic code (function read_data).
# The data is read from csv or tsv files in the settings subfolders `font`, `grammars`, `instruments`, ...
# In the following explanation each table is expected to have been imported as a record-oriented list of dicts.
# in the form [{"<col1_header>": <row1col1 value>}, "<col2_header>": <row1col2 value>,...}, ...]
#
# Structure of the DATA constant:
# <table-key>: {"section": <top level key>, "folder": <key of data subfolder>, "filename": <key of file name>,
#               "formats": <dict with formatting info>}
#
# <table-key> is the target attribute of src.settings.classes.Data that should contain the table content.
# <top level key> refers to keys in config/config.yaml that are direct children of the root.
# <key of data subfolder> and <key of file name> are the sub-keys of <top level key> that contain the folder and
#                         file name.
# <dict with formatting info> is a dict that contains information about the formatting to apply to each individual
#      record in the table. Each key of this dict corresponds with a record field name (=table column name).
#      The values consist of a tuple with three elements that have the following meaning (the last item is optional):
#         #0: <list of NotationEnum sublasses>: classes to which the (string) values should be cast. All Enum values
#                                               in the list must be unique to avoid ambiguity.
#         #1: <default value> for empty strings and missing values.
#         #2: <post-processing function>. Applied after the above casting. It should accept the entire record as
#             only argument.
#      For numeric values the first member should be an empty list.
#      Any field that does not occur in the "formats" section will be cast to str.
DATA = {
    "instruments": {
        "section": "instruments",
        "folder": "folder",
        "filename": "instruments_file",
        "formats": {
            "group": ([InstrumentGroup], None),
            "position": ([Position], None),
            "instrumenttype": ([InstrumentType], None),
            "position_range": ([Pitch], []),
            "extended_position_range": ([Pitch], []),
        },
    },
    "instrument_tags": {
        "section": "instruments",
        "folder": "folder",
        "filename": "tags_file",
        "formats": {
            "groups": ([InstrumentGroup], None),
            "positions": ([Position, RuleValue], None),
        },
    },
    "rules": {
        "section": "instruments",
        "folder": "folder",
        "filename": "rules_file",
        "formats": {
            "group": ([InstrumentGroup], None),
            "ruletype": ([RuleType], None),
            "positions": ([Position, RuleValue], None),
            "parameter1": ([RuleParameter], []),
            "value1": ([RuleValue, Pitch, Position], []),
            "parameter2": ([RuleParameter], []),
            "value2": ([RuleValue], []),
        },
    },
    "midinotes": {
        "section": "midi",
        "folder": "folder",
        "filename": "midi_definition_file",
        "formats": {
            "instrumentgroup": ([InstrumentGroup], None),
            "instrumenttype": ([InstrumentType], None),
            "positions": (
                [Position],
                None,
                lambda record: (
                    [p for p in Position if p.instrumenttype == record["instrumenttype"]]
                    if not record["positions"]
                    else record["positions"]
                ),
            ),
            "pitch": ([Pitch], Pitch.NONE),
            "octave": ([], None),
            "stroke": ([Stroke], Stroke.NONE),
            "midinote": (
                [],
                [],
                lambda record: record["midinote"] if isinstance(record["midinote"], list) else [record["midinote"]],
            ),
        },
    },
    "presets": {
        "section": "midi",
        "folder": "folder",
        "filename": "presets_file",
        "formats": {
            "instrumentgroup": ([InstrumentGroup], None),
            "instrumenttype": ([InstrumentType], None),
            "position": ([Position], None),
            "bank": ([], None),
            "preset": ([], None),
            "channel": ([], None),
            "port": ([], None),
        },
    },
    "font": {
        "section": "font",
        "folder": "folder",
        "filename": "file",
        "formats": {
            "pitch": ([Pitch], Pitch.NONE),
            "octave": ([], None),
            "stroke": ([Stroke], Stroke.NONE),
            "duration": ([], None),
            "rest_after": ([], None),
            "modifier": ([Modifier], Modifier.NONE),
        },
    },
}


# RAW CLASSES FOR DATA FILE CONTENTS
# The following preprocessing will be performed
# - Resolve all Enums defined in src.common.constants
# - Explode pseudo lists (string values containing comma separated values between square brackets)
class InstrumentRecord(BaseModel):
    group: InstrumentGroup
    position: Position
    instrument: InstrumentType


class InstrumentTagRecord(BaseModel):
    tag: str
    infile: str
    positions: list[Position]


class MidiNoteRecord(BaseModel):
    instrumentgroup: InstrumentGroup
    instrumenttype: InstrumentType
    positions: Position
    pitch: Pitch
    octave: Octave
    stroke: Stroke
    remark: str
    midinote: list[MIDIvalue]
    rootnote: str
    sample: str


class PresetRecord(BaseModel):
    instrumentgroup: InstrumentGroup
    instrumenttype: InstrumentType
    positions: Position
    bank: int
    preset: int
    channel: int
    port: int
    preset_name: str


class FontRecord(BaseModel):
    symbol: str
    unicode: str
    symbol_description: str
    balifont_symbol_description: str
    pitch: Pitch
    octave: Octave
    stroke: Stroke
    duration: Duration
    rest_after: Duration
    modifier: Modifier
    description: str

    # ANIMATION SETTINGS
    #


class InstrumentInfo(BaseModel):
    group: str
    label: str  # for instrument selector dropdown
    channels: list[int]
    midioffset: int
    animation: AnimationProfiles


class Profile(BaseModel):
    file: str
    notes: dict[NoteOct, list[int | None]]
    strokes: list[AnimationStroke]


class AnimationInfo(BaseModel):
    highlight: dict[AnimationStroke, list[str]]
    profiles: dict[AnimationProfiles, Profile]


class Part(BaseModel):
    part: str
    file: str
    loop: bool
    markers: dict[str, float] = Field(default_factory=dict)  # {partname: milliseconds}


@dataclass
class PartForm:
    # Can be used to update the values of Part objects
    # (allows to use None value if no update available)
    part: str
    file: str | None = None
    loop: bool | None = None
    markers: dict[str, float] = field(default_factory=dict)


class Song(BaseModel):
    title: str
    instrumentgroup: InstrumentGroup
    display: bool
    pdf: str | None = None
    notation_version: str = ""
    parts: list[Part] = Field(default_factory=list)


class Content(BaseModel):
    songs: list[Song]
    instrumentgroups: dict[InstrumentGroup, list[InstrumentInfo]]
    animation: AnimationInfo
    soundfont: str


# RUN SETTINGS


class RunType(StrEnum):
    RUN_SINGLE = "RUN_SINGLE"
    RUN_ALL = "RUN_ALL"


class SettingsInstrumentInfo(BaseModel):
    folder: str
    instruments_file: str
    tags_file: str
    rules_file: str
    shorthand_notation: list[Position]

    @property
    def instr_filepath(self):
        return os.path.join(self.folder, self.instruments_file)

    @property
    def tag_filepath(self):
        return os.path.join(self.folder, self.tags_file)


class SettingsMidiInfo(BaseModel):
    # Implementation of tremolo notes. First two parameters are in 1/base_note_time. E.g. if base_note_time=24, then 24 is a standard note duration.
    class TremoloInfo(BaseModel):
        notes_per_quarternote: int  # should be a divisor of base_note_time
        accelerating_pattern: list[
            int
        ]  # relative duration of the notes. Even number so that alternating note patterns end on the second note
        accelerating_velocity: list[
            int
        ]  # MIDI velocity value (0-127) for each note. Same number of values as accelerating_pattern.

    folder: str
    midi_definition_file: str
    midiversion: MidiVersion
    presets_file: str
    PPQ: int  # pulses (ticks) per quarternote
    base_note_time: int  # ticks
    base_notes_per_beat: int
    dynamics: dict[DynamicLevel, int] = Field(default_factory=dict)
    default_dynamics: DynamicLevel
    silence_seconds_before_start: int  # silence before first note
    silence_seconds_after_end: int  # silence after last note
    tremolo: TremoloInfo

    @property
    def notes_filepath(self):
        return os.path.join(self.folder, self.midi_definition_file)

    @property
    def presets_filepath(self):
        return os.path.join(self.folder, self.presets_file)


class SettingsFontInfo(BaseModel):
    folder: str
    file: str
    ttf_file: str | None

    @property
    def filepath(self):
        return os.path.join(self.folder, self.file)

    @property
    def ttf_filepath(self):
        return os.path.join(self.folder, self.ttf_file)


class SettingsGrammarInfo(BaseModel):

    folder: str
    notationfile: str
    metadatafile: str
    picklefile: str
    fontfile: str

    @property
    def notation_filepath(self) -> str:
        return os.path.normpath(os.path.abspath(os.path.join(os.path.expanduser(self.folder), self.notationfile)))

    @property
    def pickle_filepath(self) -> str:
        return os.path.normpath(os.path.abspath(os.path.join(os.path.expanduser(self.folder), self.picklefile)))

    @property
    def metadata_filepath(self) -> str:
        return os.path.normpath(os.path.abspath(os.path.join(os.path.expanduser(self.folder), self.metadatafile)))

    @property
    def font_filepath(self) -> str:
        return os.path.normpath(os.path.abspath(os.path.join(os.path.expanduser(self.folder), self.fontfile)))


class SettingsSampleInfo(BaseModel):
    folder: str
    subfolder: str


class SettingsSoundfontInfo(BaseModel):
    folder: str
    path_to_viena_app: str
    definition_file_out: str = None
    soundfont_file_out: str = None
    soundfont_destination_folders: list[str] = Field(default_factory=list)

    @property
    def def_filepath(self) -> str:
        return os.path.normpath(
            os.path.abspath(os.path.join(os.path.expanduser(self.folder), self.definition_file_out))
        )

    @property
    def sf_filepath_list(self) -> list[str]:
        return [
            os.path.normpath(os.path.abspath(os.path.join(os.path.expanduser(folder), self.soundfont_file_out)))
            for folder in self.soundfont_destination_folders  # pylint: disable=not-an-iterable
        ]


class SettingsMidiPlayerInfo(BaseModel):
    folder: str
    contentfile: str
    helpinghand: list[Position] = None


class SettingsPdfConverterInfo(BaseModel):
    folder: str
    fonts: dict[str, str] = Field(default_factory=dict)
    version_fmt: str


class SettingsNotationInfo(BaseModel):
    class NotationPart(BaseModel):
        name: str
        file: str
        loop: bool

    title: str
    subfolder: str
    instrumentgroup: InstrumentGroup
    fontversion: NotationFontVersion
    parts: dict[str, NotationPart] = Field(default_factory=dict)
    version_fmt: str
    folder_in: str
    folder_out_nonprod: str
    folder_out_prod: str
    midi_out_file_pattern: str
    pdf_out_file_pattern: str
    # IDs of the parts for which to generate a PDF notation document
    generate_pdf_part_ids: list[str] = Field(default_factory=list)
    beat_at_end: bool
    autocorrect_kempyung: bool
    # run types that should include this composition
    include_in_run_types: list[RunType] = Field(default_factory=list)
    include_in_production_run: bool
    part: NotationPart = None


class SettingsOptions(BaseModel):
    class NotationToMidiOptions(BaseModel):
        runtype: RunType
        detailed_validation_logging: bool
        autocorrect: bool
        save_corrected_to_file: bool
        save_pdf_notation: bool
        save_midifile: bool
        is_production_run: bool
        is_integration_test: bool = False

        @property
        def update_midiplayer_content(self) -> bool:
            return self.is_production_run

    class SoundfontOptions(BaseModel):
        run: bool
        create_sf2_files: bool

    debug_logging: bool
    notation_to_midi: NotationToMidiOptions | None = None
    soundfont: SoundfontOptions | None = None


class Data(BaseModel):
    # Contains pre-formatted table data
    font: list[dict[str, Any]] | None
    instruments: list[dict[str, Any]] | None
    instrument_tags: list[dict[str, Any]] | None
    rules: list[dict[str, Any]] | None
    midinotes: list[dict[str, Any]] | None
    presets: list[dict[str, Any]] | None


class ConfigData(BaseModel):
    instruments: SettingsInstrumentInfo
    midi: SettingsMidiInfo
    font: SettingsFontInfo
    grammar: SettingsGrammarInfo
    samples: SettingsSampleInfo
    soundfont: SettingsSoundfontInfo
    midiplayer: SettingsMidiPlayerInfo
    pdf_converter: SettingsPdfConverterInfo
    notations: dict[str, SettingsNotationInfo] = Field(default_factory=dict)


class RunSettings(BaseModel):
    """Contains all configuration and settings data.
    Do not instantiate this class, but call src.settings.settings.Settings.get(...)
    to get a RunSettings instance."""

    midiversion: str | None = None
    notation_id: str | None = None
    part_id: str | None = None
    options: SettingsOptions
    configdata: ConfigData
    data: Data = None

    def __init__(self):
        """Initializes an instance and populates it from the config/settings yaml files in the settings folder."""
        settings = self._load_run_settings()
        super().__init__(**settings)  # pylint: disable=not-a-mapping

    @property
    def notation(self) -> SettingsNotationInfo:
        notation = self.configdata.notations[self.notation_id]
        return notation.model_copy(update={"part": notation.parts[self.part_id]})

    @property
    def midi(self) -> SettingsMidiInfo:
        return self.configdata.midi

    @property
    def font(self) -> SettingsFontInfo:
        return self.configdata.font

    @property
    def grammar(self) -> SettingsGrammarInfo:
        return self.configdata.grammar

    @property
    def midiplayer(self) -> SettingsMidiPlayerInfo:
        return self.configdata.midiplayer

    @property
    def pdf_converter(self) -> SettingsPdfConverterInfo:
        return self.configdata.pdf_converter

    @property
    def instrumentgroup(self) -> InstrumentGroup:
        return self.notation.instrumentgroup

    @property
    def fontversion(self) -> NotationFontVersion:
        return self.notation.fontversion

    @property
    def midi_out_file(self) -> str:
        return self.notation.midi_out_file_pattern.format(title=self.notation.title, part_id=self.part_id)

    @property
    def pdf_out_file(self) -> str:
        return self.notation.pdf_out_file_pattern.format(title=self.notation.title, part_id=self.part_id)

    @property
    def folder_out(self) -> str:
        return (
            self.notation.folder_out_prod
            if self.options.notation_to_midi.is_production_run
            else self.notation.folder_out_nonprod
        )

    @property
    def notation_filepath(self) -> str:
        return os.path.join(self.notation.folder_in, self.notation.parts[self.part_id].file)

    @property
    def midi_out_filepath(self) -> str:
        return os.path.join(self.folder_out, self.midi_out_file)

    @property
    def pdf_out_filepath(self) -> str:
        return os.path.join(self.folder_out, self.pdf_out_file)

    @property
    def notation_datetime(self) -> datetime:
        """Returns the last modification date of the input file"""
        try:
            modification_time = os.path.getmtime(self.notation_filepath)
        except OSError:
            return None
        return datetime.fromtimestamp(modification_time)

    @property
    def notation_version(self) -> str:
        """Returns the last modification date of the input file"""
        notation_dt = self.notation_datetime
        if notation_dt:
            return notation_dt.strftime(self.notation.version_fmt).lower()
        return ""

    def _post_process(self, subdict: dict[str, Any], run_settings_dict: dict[str, Any] = None, curr_path: list = None):
        """This function enables references to yaml key values using ${<yaml_path>} notation.
        e.g.: ${notations.defaults.include_in_production_run}
        The function substitutes these references with the corresponding yaml settings values.
        Does not (yet) implement usage of references within a list structure.

        Args:
            subdict (dict[str, Any]): Part of a yaml stucture in Python format for which to substitute references.
            run_settings_dict(dict[str, Any]): Full yaml structure in Python dict format.
        """
        found: re.Match
        curr_path = curr_path or []

        for key, value in subdict.items():
            if isinstance(value, dict):
                # Iterate through dict structures until a root node is found
                sub_path = curr_path + [key]
                subdict[key] = self._post_process(value, run_settings_dict or subdict, sub_path)
            elif isinstance(value, str):
                # Only implemented for key: str items. Does not operate on list structures (yet)
                # Determine if a ${<yaml_path>} string ioccurs in the value.
                while found := re.search(r"\$\{\{(?P<item>[\w\.]+)\}\}", value):
                    keys = found.group("item").split(".")
                    # Replace '_PARENT_' literal with current path. Should be the first item in the list.
                    if keys[0].upper() == "_PARENT_":
                        keys = curr_path + keys[1:]
                    item = run_settings_dict
                    for key1 in keys:
                        item = item[key1]
                    if found.group(0) == value:
                        # Value is a reference to a key value.
                        value = item
                        break
                    else:
                        # Value is a string containing one or more ${...} references.
                        # Substitute the sub-expression in the string.
                        value = value.replace(found.group(0), item)
                subdict[key] = value
        return subdict

    def _read_settings(self, filepath: str) -> dict:
        """Retrieves settings from the given (YAML) file. The folder is retrieved from the environment.

        Args:
            filename (str): YAML file name.

        Returns:
            dict: dict containing all the settings contained in the file.
        """
        with open(filepath, "r", encoding="utf-8") as settingsfile:
            return yaml.load(settingsfile, yaml.Loader)

    def _read_data(self, settings_dict: dict, specs: dict) -> dict[str, list[dict[str, str]]]:
        """Reads multiple data files into table-like dict structures. Columns that appear in the 'format' section
        of the specs will be formatted accordingly.
        Args:
            settings_dict (dict): dict containing run settings
            specs: (dict): dict containing information about the data to retrieve.
                The values refer to keys in the settings dict. Format:
                {<table1-key>:
                    {"section": <top level key>, "folder": <key of data subfolder>, "filename": <key of file name>, "formats" : <formatting>},
                <table2-key>: ...
                }
                where <formatting> is a tuple (list[<NotationEnum class>], <value if missing or none>)
        Returns:
            dict[str, list[dict[str, str]]]: dict table-key -> <list of records> where each record represents a row.
        """
        data = {}
        for item, entry in specs.items():
            category = entry["section"]
            folder = settings_dict[category][entry["folder"]]
            file = settings_dict[category][entry["filename"]]
            filepath = os.path.join(folder, file)
            data[item] = (
                pd.read_csv(filepath, sep="\t", comment="#", dtype=str)
                .replace([np.nan], [""], regex=False)
                .to_dict(orient="records")
            )
            if "formats" in entry:
                for fmtcolumn, formatting in entry["formats"].items():
                    for record in data[item]:
                        if fmtcolumn in record:
                            if not record[fmtcolumn]:
                                # format missing value
                                record[fmtcolumn] = formatting[1]
                            else:
                                mapping = {
                                    strval: val for fmt in formatting[0] for strval, val in fmt.member_map().items()
                                }
                                record[fmtcolumn] = eval(record[fmtcolumn] or formatting[1], mapping)
                            # Apply formatting function if available
                            if len(formatting) > 2:
                                record[fmtcolumn] = formatting[2](record)
        return data

    def _validate_settings(self, data_dict: dict, run_settings_dict: dict) -> bool:
        """Checks that the notation id and part id correspond with an entry in the config file (config.yaml).
        Args:
            data_dict (dict): _description_
            run_settings_dict (dict): _description_
        Returns:
            bool: _description_
        """
        notation_id = run_settings_dict[Yaml.NOTATION_ID]
        part_id = run_settings_dict[Yaml.PART_ID]
        if not data_dict[Yaml.NOTATIONS].get(notation_id, None):
            logger.error("Invalid composition name: %s", notation_id)
            return False
        if not data_dict[Yaml.NOTATIONS][Yaml.NOTATION_ID].get(part_id, None):
            logger.error("Part %s not found in composition %s", part_id, notation_id)
            return False
        return True

    def _load_run_settings(self):
        """Retrieves the run settings from the run settings yaml file, enriched with information
        from the data information yaml file.
        Be aware that this method is called automatically when python first encounters an import statement that imports
        src.common.classes (see the `_build_class` methods in that module). This is especially relevant for unit tests
        that use separate YAML settings files.

        Args:
            notation_id: key value of the notation as it appears in the config.yaml file
            part_id: key value of the part of the notation

        Returns:
            RunSettings: settings object
        """
        config_filepath = os.getenv(ENV_VAR_CONFIG_PATH)
        settings_data_dict = self._read_settings(config_filepath)
        # update each notation entry with the default settings
        for key, notation_entry in settings_data_dict[Yaml.NOTATIONS].items():
            if key == Yaml.DEFAULTS:
                continue
            settings_data_dict[Yaml.NOTATIONS][key] = settings_data_dict[Yaml.NOTATIONS][Yaml.DEFAULTS] | notation_entry
        del settings_data_dict[Yaml.NOTATIONS][Yaml.DEFAULTS]
        settings_data_dict = self._post_process(settings_data_dict)

        settings_filepath = os.getenv(ENV_VAR_N2M_SETTINGS_PATH)
        run_settings_dict = self._read_settings(settings_filepath)
        run_settings_dict[Yaml.CONFIGDATA] = settings_data_dict
        run_settings_dict[Yaml.DATA] = self._read_data(settings_data_dict, DATA)

        return run_settings_dict
