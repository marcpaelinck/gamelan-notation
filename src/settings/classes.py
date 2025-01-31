import os
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
    part: str
    file: str
    loop: bool
    markers: dict[str, float] = Field(default_factory=dict)  # {partname: milliseconds}


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
        integration_test_subfolder_in: str
        integration_test_subfolder_out: str
        is_integration_test: bool
        part: "RunSettings.NotationPart"
        midi_out_file: str
        beat_at_end: bool
        autocorrect_kempyung: bool

        @property
        def subfolderpath(self):
            return os.path.join(
                self.folder, self.integration_test_subfolder_in if self.is_integration_test else self.subfolder
            )

        @property
        def filepath(self):
            return os.path.join(self.subfolderpath, self.part.file)

        @property
        def midi_out_filepath(self):
            return os.path.join(
                self.folder,
                self.integration_test_subfolder_out if self.is_integration_test else self.subfolder,
                self.midi_out_file,
            )

        @property
        def midi_out_filepath_midiplayer(self):
            return os.path.join(self.midiplayer_folder, self.midi_out_file)

    class MidiInfo(BaseModel):
        # Implementation of tremolo notes. First two parameters are in 1/base_note_time. E.g. if base_note_time=24, then 24 is a standard note duration.
        class TremoloInfo(BaseModel):
            notes_per_quarternote: int  # should be a divisor of base_note_time
            accelerating_pattern: list[
                int
            ]  # relative duration of the notes. Even number so that alternating note patterns end on the second note
            accelerating_velocity: list[
                int
            ]  # MIDI velocity value (0-127) for each note. Same number of values as accelerating_pattern.

        midiversion: str
        folder: str
        midi_definition_file: str
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

    class SampleInfo(BaseModel):
        folder: str
        subfolder: str

    class InstrumentInfo(BaseModel):
        instrumentgroup: InstrumentGroup
        folder: str
        instruments_file: str
        tags_file: str
        rules_file: str

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

    class IntegrationTestInfo(BaseModel):
        inputfolder: str
        outputfolder: str
        notations: list[dict[str, str]]

    class GrammarInfo(BaseModel):
        folder: str
        notationfile: str
        metadatafile: str
        fontfile: str
        picklefile: str

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
        helpinghand: list[Position] = None

    class Options(BaseModel):
        class NotationToMidiOptions(BaseModel):
            run: bool
            detailed_validation_logging: bool
            autocorrect: bool
            save_corrected_to_file: bool
            save_midifile: bool
            update_midiplayer_content: bool
            integration_test: bool

        class SoundfontOptions(BaseModel):
            run: bool
            create_sf2_files: bool

        debug_logging: bool
        validate_settings: bool
        notation_to_midi: NotationToMidiOptions | None = None
        soundfont: SoundfontOptions | None = None

    class Data(BaseModel):
        # Contains pre-formatted table data
        font: list[dict[str, str | None]] | None
        instruments: list[dict[str, str | None]] | None
        instrument_tags: list[dict[str, str | None]] | None
        rules: list[dict[str, str | None]] | None
        midinotes: list[dict[str, str | None]] | None
        presets: list[dict[str, str | None]] | None

    # attributes of class RunSettings
    options: Options
    midi: MidiInfo | None = None
    midiplayer: MidiPlayerInfo | None = None
    soundfont: SoundfontInfo | None = None
    samples: SampleInfo | None = None
    notation: NotationInfo | None = None
    instruments: InstrumentInfo | None = None
    font: FontInfo | None = None
    grammars: GrammarInfo | None = None
    integration_test: IntegrationTestInfo | None = None
    data: Data
