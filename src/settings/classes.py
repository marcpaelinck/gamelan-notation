import os
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any

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
    Stroke,
)


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
    docx_template: str
    version_fmt: str
    fonts: dict[str, str] = Field(default_factory=dict)


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
    validate_settings: bool
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
    midiversion: str | None = None
    notation_id: str | None = None
    part_id: str | None = None
    options: SettingsOptions
    configdata: ConfigData
    data: Data = None

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
    def midi_out_file(self):
        return self.notation.midi_out_file_pattern.format(title=self.notation.title, part_id=self.part_id)

    @property
    def pdf_out_file(self):
        return self.notation.pdf_out_file_pattern.format(title=self.notation.title, part_id=self.part_id)

    @property
    def folder_out(self):
        return (
            self.notation.folder_out_prod
            if self.options.notation_to_midi.is_production_run
            else self.notation.folder_out_nonprod
        )

    @property
    def notation_filepath(self):
        return os.path.join(self.notation.folder_in, self.notation.parts[self.part_id].file)

    @property
    def midi_out_filepath(self):
        return os.path.join(self.folder_out, self.midi_out_file)

    @property
    def pdf_out_filepath(self):
        return os.path.join(self.folder_out, self.pdf_out_file)
