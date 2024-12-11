import json
import logging
import os
import re
from collections import defaultdict
from dataclasses import dataclass, field
from enum import StrEnum, auto
from typing import Generator, Optional

from pydantic import (
    BaseModel,
    ConfigDict,
    computed_field,
    field_validator,
    model_validator,
)

from src.common.constants import (
    BPM,
    DEFAULT,
    PASS,
    Duration,
    InstrumentGroup,
    InstrumentPosition,
    InstrumentType,
    Modifier,
    NotationDict,
    NotationFont,
    Octave,
    Pass,
    Pitch,
    Stroke,
)
from src.common.logger import get_logger
from src.common.metadata_classes import (
    GonganType,
    GoToMeta,
    MetaData,
    MetaDataType,
    ValidationProperty,
)
from src.common.playercontent_classes import Part


@dataclass
class TimedMessage:
    time: int
    type: str
    note: str = "."
    cumtime: int = -1
    duration: int = -1


@dataclass
class TimingData:
    unit_duration: int
    units_per_beat: int
    beats_per_gongan: int


class ParserModel:
    class ParserType(StrEnum):
        NOTATIONPARSER = "parsing the notation"
        SCOREGENERATOR = "generating the score"
        VALIDATOR = "validating the score"
        MIDIGENERATOR = "generating the midi file"

    parser_type: ParserType
    run_settings = None
    curr_gongan_id: int = None
    curr_beat_id: int = None
    curr_position: InstrumentPosition = None
    errors = []
    logger = None

    def __init__(self, parser_type: ParserType, run_settings: "RunSettings"):
        self.parser_type = parser_type
        self.run_settings = run_settings
        self.logger = get_logger(self.__class__.__name__)

    def log(self, err_msg: str, level: logging = logging.ERROR) -> str:
        prefix = (
            f"{self.curr_gongan_id:02d}-{self.curr_beat_id:02d} | "
            if self.curr_beat_id
            else f"{self.curr_gongan_id:02d}    | "
        )
        if level > logging.INFO:
            if not self.errors:
                self.logger.error(f"Errors encountered while {self.parser_type.value}:")
            msg = "     " + prefix + err_msg
            self.logger.log(level, msg)
            if level > logging.INFO:
                self.errors.append(msg)

    def logerror(self, msg: str) -> str:
        self.log(msg, level=logging.ERROR)

    def logwarning(self, msg: str) -> str:
        self.log(msg, level=logging.WARNING)

    def loginfo(self, msg: str) -> str:
        self.log(msg, level=logging.INFO)

    """Use the following generators to iterate through gongans and beats if you 
    want to use the logging methods of this class. This will ensure that the the 
    logging is prefixed with the correct gongan and beat ids.
    """

    def gongan_iterator(self, score: "Score"):
        for gongan in score.gongans:
            self.curr_gongan_id = gongan.id
            self.curr_beat_id = None
            yield gongan

    def beat_iterator(self, gongan: "Gongan"):
        for beat in gongan.beats:
            self.curr_beat_id = beat.id
            yield beat

    @property
    def has_errors(self):
        return len(self.errors) > 0


# Settings
class NotationModel(BaseModel):
    @classmethod
    def to_list(cls, value, el_type: type):
        # This method tries to to parse a string or a list of strings
        # into a list of `el_type` values.
        # el_type can only be `float` or a subclass of `StrEnum`.
        if isinstance(value, str):
            # Single string representing a list of strings: parse into a list of strings
            # First add double quotes around each list element.
            val = re.sub(r"([A-Za-z_][\w]*)", r'"\1"', value)
            value = json.loads(val)
        if isinstance(value, list):
            # List of strings: convert strings to enumtype objects.
            if all(isinstance(el, str) for el in value):
                return [el_type[el] if issubclass(el_type, StrEnum) else float(el) for el in value]
            elif all(isinstance(el, el_type) for el in value):
                # List of el_type: do nothing
                return value
        else:
            raise ValueError(f"Cannot convert value {value} to a list of {el_type}")


class Note(NotationModel):
    model_config = ConfigDict(extra="ignore", frozen=True)

    position: InstrumentPosition
    symbol: str
    # symbolvalue: SymbolValue  # Phase out
    pitch: Pitch
    octave: Optional[int]
    stroke: Stroke
    duration: Optional[float]
    rest_after: Optional[float]
    velocity: Optional[int] = 127
    modifier: Modifier
    midinote: list[int] = 127  # 0..128, used when generating MIDI output.
    rootnote: Optional[str] = ""
    sample: str = ""  # file name of the (mp3) sample.
    _validate_range: bool = True

    @property
    def total_duration(self):
        return self.duration + self.rest_after

    @field_validator("octave", mode="before")
    @classmethod
    def process_nonevals(cls, value):
        if isinstance(value, str) and value.upper() == "NONE":
            return None
        return value

    @classmethod
    @model_validator(mode="after")
    def validate_note(self):
        if not self._validate_range:
            return self
        # Delay import of the lookup to avoid circular reference.
        from src.common.lookups import LOOKUP

        if self.position not in LOOKUP.POSITION_P_O_S_TO_NOTE.keys():
            self._errormsg = f"No range information for {self.position}"
            return None
        if (self.pitch, self.octave, self.stroke) not in LOOKUP.POSITION_P_O_S_TO_NOTE[self.position]:
            self._errormsg = f"{self.pitch} OCT{self.octave} {self.stroke} not in range of {self.position}"
            return None
        return self

    def matches(self, pitch: Pitch, octave: Octave, stroke: Stroke, duration: Duration, rest_after: Duration) -> bool:
        return (
            pitch == self.pitch
            and self.stroke == stroke
            and self.duration == duration
            and (self.octave == octave or octave is None)
            and (self.rest_after == rest_after or rest_after is None)
        )


class Preset(NotationModel):
    # See http://www.synthfont.com/The_Definitions_File.pdf
    # For port, see https://github.com/spessasus/SpessaSynth/wiki/About-Multi-Port
    instrumenttype: InstrumentType
    position: InstrumentPosition
    bank: int  # 0..127, where 127 is reserved for percussion instruments.
    preset: int  # 0..127
    channel: int  # 0..15
    port: int  # 0..255
    preset_name: str


class MidiNote(NotationModel):
    instrumenttype: InstrumentType
    positions: list[InstrumentPosition]
    pitch: Pitch
    octave: Optional[int]
    stroke: Stroke
    midinote: list[int]  # 0..128, used when generating MIDI output.
    rootnote: Optional[str]
    sample: str  # file name of the (mp3) sample.
    # preset: Preset
    remark: str

    @field_validator("positions", mode="before")
    @classmethod
    def validate_pos(cls, value):
        return cls.to_list(value, InstrumentPosition)

    @field_validator("octave", mode="before")
    @classmethod
    def process_nonevals(cls, value):
        if isinstance(value, str) and value.upper() == "NONE":
            return None
        return value


class InstrumentTag(NotationModel):
    tag: str
    positions: list[InstrumentPosition]
    infile: str = ""

    @field_validator("positions", mode="before")
    @classmethod
    def validate_pos(cls, value):
        return cls.to_list(value, InstrumentPosition)


#
# Flow
#


@dataclass
class Beat:
    @dataclass
    class TempoChange:
        new_tempo: BPM
        steps: int = 0
        incremental: bool = False

    @dataclass
    class Repeat:
        class RepeatType(StrEnum):
            GONGAN = auto()
            BEAT = auto()

        goto: "Beat"
        iterations: int
        kind: RepeatType = RepeatType.GONGAN
        _countdown: int = 0

        def reset(self):
            self._countdown = self.iterations

    id: int
    sys_id: int
    bpm_start: dict[PASS, BPM]  # tempo at beginning of beat (can vary per pass)
    bpm_end: dict[PASS, BPM]  # tempo at end of beat (can vary per pass)
    duration: float
    tempo_changes: dict[PASS, TempoChange] = field(default_factory=dict)
    staves: dict[InstrumentPosition, list[Note]] = field(default_factory=dict)
    # Exceptions contains alternative staves for specific passes.
    exceptions: dict[(InstrumentPosition, Pass), list[Note]] = field(default_factory=dict)
    prev: "Beat" = field(default=None, repr=False)  # previous beat in the score
    next: "Beat" = field(default=None, repr=False)  # next beat in the score
    goto: dict[PASS, "Beat"] = field(
        default_factory=dict
    )  # next beat to be played according to the flow (GOTO metadata)
    has_kempli_beat: bool = True
    repeat: Repeat = None
    validation_ignore: list[ValidationProperty] = field(default_factory=list)
    _pass_: PASS = 0  # Counts the number of times the beat is passed during generation of MIDI file.

    @computed_field
    @property
    def full_id(self) -> str:
        return f"{int(self.sys_id)}-{self.id}"

    @computed_field
    @property
    def sys_seq(self) -> int:
        # Returns the pythonic sequence id (numbered from 0)
        return self.sys_id - 1

    def next_beat_in_flow(self, pass_=None):
        return self.goto.get(pass_ or self._pass_, self.next)

    def get_bpm_start(self):
        return self.bpm_start.get(self._pass_, self.bpm_start.get(DEFAULT, None))

    def get_bpm_end(self):
        return self.bpm_end.get(self._pass_, self.bpm_end.get(DEFAULT, None))

    def get_bpm_end_last_pass(self):
        return self.bpm_end.get(self._pass_, self.bpm_end.get(DEFAULT, None))

    def get_changed_tempo(self, current_tempo: BPM) -> BPM | None:
        tempo_change = self.tempo_changes.get(self._pass_, self.tempo_changes.get(DEFAULT, None))
        if tempo_change and tempo_change.new_tempo != current_tempo:
            if tempo_change.incremental:
                return current_tempo + int((tempo_change.new_tempo - current_tempo) / tempo_change.steps)
            else:
                return tempo_change.new_tempo
        return None


@dataclass
class Gongan:
    # A set of beats.
    # A Gongan consists of a set of instrument parts.
    # Gongans in the input file are separated from each other by an empty line.
    id: int
    beats: list[Beat] = field(default_factory=list)
    beat_duration: int = 4
    gongantype: GonganType = GonganType.REGULAR
    metadata: list[MetaData] = field(default_factory=list)
    comments: list[str] = field(default_factory=list)
    _pass_: PASS = 0  # Counts the number of times the gongan is passed during generation of MIDI file.

    def get_metadata(self, cls: MetaDataType):
        return next((meta.data for meta in self.metadata if isinstance(meta.data, cls)), None)


@dataclass
class FlowInfo:
    # Keeps track of statements that modify the sequence of
    # gongans or beats in the score. The main purpose of this
    # class is to keep track of gotos that point to labels that
    # have not yet been encountered while processing the score.
    labels: dict[str, Beat] = field(default_factory=dict)
    gotos: dict[str, tuple[Gongan, GoToMeta]] = field(default_factory=lambda: defaultdict(list))


@dataclass
class Notation:
    notation_dict: NotationDict
    settings: "RunSettings"


@dataclass
class Score:

    title: str
    settings: "RunSettings"
    instrument_positions: set[InstrumentPosition] = None
    gongans: list[Gongan] = field(default_factory=list)
    midi_notes_dict: dict[tuple[InstrumentPosition, Pitch, Octave, Stroke], MidiNote] = None
    position_range_lookup: dict[InstrumentPosition, tuple[Pitch, Octave, Stroke]] = None
    flowinfo: FlowInfo = field(default_factory=FlowInfo)
    total_duration: float | None = None
    midifile_length: int = None


#
# # RUN SETTINGS
#


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

    # attributes of class RunSettings
    options: Options
    midi: MidiInfo
    midiplayer: MidiPlayerInfo
    soundfont: SoundfontInfo
    samples: SampleInfo
    notation: Optional[NotationInfo] = None
    instruments: Optional[InstrumentInfo] = None
    font: Optional[FontInfo] = None
