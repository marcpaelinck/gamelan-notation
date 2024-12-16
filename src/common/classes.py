import json
import re
from collections import defaultdict
from dataclasses import dataclass, field
from enum import StrEnum, auto
from typing import ClassVar

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
    InstrumentType,
    Modifier,
    NotationDict,
    Octave,
    Pass,
    Pitch,
    Position,
    Stroke,
    Velocity,
)
from src.common.metadata_classes import (
    GonganType,
    GoToMeta,
    MetaData,
    MetaDataType,
    ValidationProperty,
)
from src.settings.classes import RunSettings
from src.settings.font_to_valid_notes import get_note_records
from src.settings.settings import get_run_settings


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


class NotationModel(BaseModel):
    # Class model containing common utilities.

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
    # config revalidate_instances forces validation when using model_copy
    model_config = ConfigDict(extra="ignore", frozen=True, revalidate_instances="always")

    VALIDNOTES: ClassVar[list[dict]] = get_note_records(get_run_settings())

    instrumenttype: InstrumentType
    position: Position
    symbol: str
    pitch: Pitch
    octave: int | None
    stroke: Stroke
    duration: float | None
    rest_after: float | None
    velocity: int = 127
    modifier: Modifier
    midinote: list[int] = [127]  # 0..128, used when generating MIDI output.
    rootnote: str = ""
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
    position: Position
    bank: int  # 0..127, where 127 is reserved for percussion instruments.
    preset: int  # 0..127
    channel: int  # 0..15
    port: int  # 0..255
    preset_name: str


class MidiNote(NotationModel):
    instrumenttype: InstrumentType
    positions: list[Position]
    pitch: Pitch
    octave: int | None
    stroke: Stroke
    midinote: list[int]  # 0..128, used when generating MIDI output.
    rootnote: str | None
    sample: str  # file name of the (mp3) sample.
    # preset: Preset
    remark: str

    @field_validator("positions", mode="before")
    @classmethod
    def validate_pos(cls, value):
        return cls.to_list(value, Position)

    @field_validator("octave", mode="before")
    @classmethod
    def process_nonevals(cls, value):
        if isinstance(value, str) and value.upper() == "NONE":
            return None
        return value


class InstrumentTag(NotationModel):
    tag: str
    positions: list[Position]
    infile: str = ""

    @field_validator("positions", mode="before")
    @classmethod
    def validate_pos(cls, value):
        return cls.to_list(value, Position)


#
# Flow
#


# Note: Beat is intentionally not a Pydantic subclass because
# it points to itself through the `next`, `prev` and `goto` fields,
# which would otherwise cause an "Infinite recursion" error.
@dataclass
class Beat:

    class Change(NotationModel):
        # NotationModel contains a method to translate a list-like string to an actual list.
        class Type(StrEnum):
            TEMPO = auto()
            DYNAMICS = auto()

        # A change in tempo or velocity.
        new_value: int
        steps: int = 0
        incremental: bool = False
        positions: list[Position] = field(default_factory=list)

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
    gongan_id: int
    bpm_start: dict[PASS, BPM]  # tempo at beginning of beat (can vary per pass)
    bpm_end: dict[PASS, BPM]  # tempo at end of beat (can vary per pass)
    velocities_start: dict[PASS, dict[Position, Velocity]]  # Same for velocity, specified per position
    velocities_end: dict[PASS, dict[Position, Velocity]]
    duration: float
    changes: dict[Change.Type, dict[PASS, Change]] = field(default_factory=lambda: defaultdict(dict))
    staves: dict[Position, list[Note]] = field(default_factory=dict)
    # Exceptions contains alternative staves for specific passes.
    exceptions: dict[(Position, Pass), list[Note]] = field(default_factory=dict)
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
        return f"{int(self.gongan_id)}-{self.id}"

    @computed_field
    @property
    def gongan_seq(self) -> int:
        # Returns the pythonic sequence id (numbered from 0)
        return self.gongan_id - 1

    def next_beat_in_flow(self, pass_=None):
        return self.goto.get(pass_ or self._pass_, self.next)

    def get_bpm_start(self):
        return self.bpm_start.get(self._pass_, self.bpm_start.get(DEFAULT, None))

    def get_velocity_start(self, position):
        velocities_start = self.velocities_start.get(self._pass_, self.velocities_start.get(DEFAULT, None))
        # NOTE intentionally causing Exception if position not in velocities_start
        return velocities_start[position]

    def get_changed_value(
        self, current_value: BPM | Velocity, position: Position, changetype: Change.Type
    ) -> BPM | Velocity | None:
        # Generic function, returns either a BPM or a Velocity value for the current beat.
        # Returns None if the value for the current beat is the same as that of the previous beat.
        # In case of a gradual change over several measures, calculates the value for the current beat.
        change_list = self.changes[changetype]
        change = change_list.get(self._pass_, change_list.get(DEFAULT, None))
        if change and changetype is Beat.Change.Type.DYNAMICS and position not in change.positions:
            change = None
        if change and change.new_value != current_value:
            if change.incremental:
                return current_value + int((change.new_value - current_value) / change.steps)
            else:
                return change.new_value
        return None

    @classmethod
    def get_default_velocities(cls) -> dict[Position, Velocity]:
        from src.common.lookups import LOOKUP

        default_velocity = LOOKUP.DYNAMICS_TO_VELOCITY[LOOKUP.DEFAULT_DYNAMICS]
        return {pos: default_velocity for pos in Position}


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
    instrument_positions: set[Position] = None
    gongans: list[Gongan] = field(default_factory=list)
    midi_notes_dict: dict[tuple[Position, Pitch, Octave, Stroke], MidiNote] = None
    position_range_lookup: dict[Position, tuple[Pitch, Octave, Stroke]] = None
    flowinfo: FlowInfo = field(default_factory=FlowInfo)
    midifile_duration: int = None
