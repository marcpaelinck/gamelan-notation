import os
from enum import Enum, StrEnum
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


class RunType(StrEnum):
    RUN_SINGLE = "RUN_SINGLE"
    RUN_SINGLE_PRODUCTION = "RUN_SINGLE_PRODUCTION"
    RUN_ALL = "RUN_ALL"
    RUN_ALL_PRODUCTION = "RUN_ALL_PRODUCTION"


class RunSettings(BaseModel):
    class NotationPart(BaseModel):
        name: str
        file: str
        loop: bool

    class NotationInfo(BaseModel):
        class FolderInfo(BaseModel):
            folder_in: str
            folder_out: str

        title: str
        instrumentgroup: InstrumentGroup
        midi_out_file: str
        pdf_out_file: str
        run_type: RunType
        folders: dict[RunType, FolderInfo] = Field(default_factory=dict)
        subfolder: str
        part_id: str = ""
        parts: dict[str, "RunSettings.NotationPart"] = Field(default_factory=dict)
        beat_at_end: bool
        autocorrect_kempyung: bool
        # run types that should include this composition
        include_in_run_types: list[RunType] = Field(default_factory=list)
        generate_pdf_part_ids: list[str] = Field(default_factory=list)
        production: bool  # resulting MIDI file fit to save to production environment?

        @property
        def part(self):
            return self.parts[self.part_id] if self.part_id in self.parts.keys() else None

        @property
        def notation_filepath(self):
            return os.path.join(self.folders[self.run_type].folder_in, self.parts[self.part_id].file)

        @property
        def midi_out_filepath(self):
            return os.path.join(self.folders[self.run_type].folder_out, self.midi_out_file)

        @property
        def pdf_out_filepath(self):
            return os.path.join(self.folders[self.run_type].folder_out, self.pdf_out_file)

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
        ttf_file: str

        @property
        def filepath(self):
            return os.path.join(self.folder, self.file)

        @property
        def ttf_filepath(self):
            return os.path.join(self.folder, self.ttf_file)

    class MultipleRunsInfo(BaseModel):
        folder_in: str
        folder_out: str
        runtype: RunType
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

    class PdfConverterInfo(BaseModel):
        folder: str
        docx_template: str
        fonts: dict[str, str] = Field(default_factory=dict)

    class Options(BaseModel):
        class NotationToMidiOptions(BaseModel):
            runtype: RunType
            detailed_validation_logging: bool
            autocorrect: bool
            save_corrected_to_file: bool
            save_pdf_notation: bool
            save_midifile: bool
            is_integration_test: bool = False

            @property
            def update_midiplayer_content(self) -> bool:
                return self.runtype in [RunType.RUN_ALL, RunType.RUN_SINGLE_PRODUCTION]

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
    notations: dict[str, NotationInfo] = Field(default_factory=dict)
    notation: NotationInfo | None = None
    multiple_runs: MultipleRunsInfo | None = None
    instruments: InstrumentInfo | None = None
    font: FontInfo | None = None
    grammars: GrammarInfo | None = None
    pdf_converter: PdfConverterInfo | None = None
    data: Data
