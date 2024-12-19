import os
from typing import Any

from pydantic import BaseModel, Field

from src.common.constants import (
    AnimationProfiles,
    Duration,
    DynamicLevel,
    InstrumentGroup,
    InstrumentType,
    MIDIvalue,
    Modifier,
    NotationFont,
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


class Part(BaseModel):
    name: str
    file: str
    loop: bool
    markers: dict[str, float] = Field(default_factory=dict)  # {partname: milliseconds}


class InstrumentInfo(BaseModel):
    name: str
    channels: list[int]
    midioffset: int
    animation: AnimationProfiles


class Profile(BaseModel):
    file: str
    notes: dict[NoteOct, list[int | None]]
    strokes: list[Stroke]


class AnimationInfo(BaseModel):
    highlight: dict[Stroke, list[str]]
    profiles: dict[AnimationProfiles, Profile]


class Song(BaseModel):
    title: str
    instrumentgroup: InstrumentGroup
    display: bool
    parts: list[Part] = Field(default_factory=list)


class Content(BaseModel):
    songs: list[Song]
    instrumentgroups: dict[InstrumentGroup, list[InstrumentInfo]]
    animation: AnimationInfo
    soundfont: str


# RUN SETTINGS


class RunSettings(BaseModel):
    class NotationPart(BaseModel):
        name: str
        file: str
        loop: bool

    class NotationInfo(BaseModel):
        title: str
        instrumentgroup: InstrumentGroup
        folder: str
        subfolder: str
        midiplayer_folder: str
        part: Part
        midi_out_file: str
        beat_at_end: bool
        autocorrect_kempyung: bool

        @property
        def subfolderpath(self):
            return os.path.join(self.folder, self.subfolder)

        @property
        def filepath(self):
            return os.path.join(self.folder, self.subfolder, self.part.file)

        @property
        def midi_out_filepath(self):
            return os.path.join(self.folder, self.subfolder, self.midi_out_file)

        @property
        def midi_out_filepath_midiplayer(self):
            return os.path.join(self.midiplayer_folder, self.midi_out_file)

    class MidiInfo(BaseModel):
        midiversion: str
        folder: str
        midi_definition_file: str
        presets_file: str
        PPQ: int  # pulses per quarternote
        dynamics: dict[DynamicLevel, int] = Field(default_factory=dict)
        default_dynamics: DynamicLevel

        @property
        def notes_filepath(self):
            return os.path.join(self.folder, self.midi_definition_file)

        @property
        def presets_filepath(self):
            return os.path.join(self.folder, self.presets_file)

    class SampleInfo(BaseModel):
        folder: str
        subfolder: str

    class InstrumentInfo(BaseModel):
        instrumentgroup: InstrumentGroup
        folder: str
        instruments_file: str
        tags_file: str

        @property
        def instr_filepath(self):
            return os.path.join(self.folder, self.instruments_file)

        @property
        def tag_filepath(self):
            return os.path.join(self.folder, self.tags_file)

    class FontInfo(BaseModel):
        fontversion: NotationFont
        folder: str
        file: str

        @property
        def filepath(self):
            return os.path.join(self.folder, self.file)

    class SoundfontInfo(BaseModel):
        folder: str
        path_to_viena_app: str
        definition_file_out: str
        soundfont_file_out: str
        soundfont_destination_folders: list[str]

        @property
        def def_filepath(self) -> str:
            return os.path.normpath(
                os.path.abspath(os.path.join(os.path.expanduser(self.folder), self.definition_file_out))
            )

        @property
        def sf_filepath_list(self) -> list[str]:
            return [
                os.path.normpath(os.path.abspath(os.path.join(os.path.expanduser(folder), self.soundfont_file_out)))
                for folder in self.soundfont_destination_folders
            ]

    class MidiPlayerInfo(BaseModel):
        folder: str
        contentfile: str

    class Options(BaseModel):
        class NotationToMidiOptions(BaseModel):
            run: bool
            detailed_validation_logging: bool
            autocorrect: bool
            save_corrected_to_file: bool
            save_midifile: bool
            update_midiplayer_content: bool

        class SoundfontOptions(BaseModel):
            run: bool
            create_sf2_files: bool

        debug_logging: bool
        validate_settings: bool
        notation_to_midi: NotationToMidiOptions
        soundfont: SoundfontOptions

    class Data(BaseModel):
        # Contains pre-formatted table data
        font: list[dict[str, str | None]] | None
        instruments: list[dict[str, str | None]] | None
        instrument_tags: list[dict[str, str | None]] | None
        midinotes: list[dict[str, str | None]] | None
        presets: list[dict[str, str | None]] | None

    # attributes of class RunSettings
    options: Options
    midi: MidiInfo
    midiplayer: MidiPlayerInfo
    soundfont: SoundfontInfo
    samples: SampleInfo
    notation: NotationInfo | None = None
    instruments: InstrumentInfo | None = None
    font: FontInfo | None = None
    data: Data
