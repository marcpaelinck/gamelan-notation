import json
import re
from collections import defaultdict
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Optional

from pydantic import BaseModel, ConfigDict, computed_field, field_validator

from src.common.constants import (
    ALL_PASSES,
    BPM,
    PASS,
    Duration,
    InstrumentGroup,
    InstrumentPosition,
    InstrumentType,
    MidiVersion,
    Modifier,
    NotationFont,
    NoteSource,
    Octave,
    Pitch,
    Stroke,
)
from src.common.metadata_classes import (
    GonganType,
    GoToMeta,
    MetaData,
    MetaDataStatus,
    MetaDataType,
    TempoMeta,
    ValidationProperty,
)


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
    model_config = ConfigDict(extra="forbid", frozen=True)

    source: NoteSource = NoteSource.SCORE
    symbol: str
    unicode: str
    symbol_description: str
    balifont_symbol_description: str
    # symbolvalue: SymbolValue  # Phase out
    pitch: Pitch
    octave: Optional[int]
    stroke: Stroke
    duration: Optional[float]
    rest_after: Optional[float]
    velocity: Optional[int] = 100
    modifier: Modifier
    description: str

    @property
    def total_duration(self):
        return self.duration + self.rest_after

    @field_validator("octave", mode="before")
    @classmethod
    def process_nonevals(cls, value):
        if isinstance(value, str) and value.upper() == "NONE":
            return None
        return value

    def matches(self, pitch: Pitch, octave: Octave, stroke: Stroke, duration: Duration, rest_after: Duration) -> bool:
        return (
            pitch == self.pitch
            and self.octave == octave
            and self.stroke == stroke
            and self.duration == duration
            and self.rest_after == rest_after
        )


class MidiNote(NotationModel):
    instrumentgroup: InstrumentGroup
    instrumenttype: InstrumentType
    positions: list[InstrumentPosition]
    pitch: Pitch
    octave: Optional[int]
    stroke: Stroke
    channel: int
    midi: int
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
    infile: str
    positions: list[InstrumentPosition]

    @field_validator("positions", mode="before")
    @classmethod
    def validate_pos(cls, value):
        return cls.to_list(value, InstrumentPosition)


#
# Flow
#


@dataclass(frozen=True)
class Instrument:
    tag: str
    instrumenttype: InstrumentType


@dataclass
class Beat:
    @dataclass
    class TempoChange:
        new_tempo: BPM
        steps: int = 0
        incremental: bool = False

    id: int
    sys_id: int
    bpm_start: dict[PASS, BPM]  # tempo at beginning of beat (can vary per pass)
    bpm_end: dict[PASS, BPM]  # tempo at end of beat (can vary per pass)
    duration: float
    tempo_changes: dict[PASS, TempoChange] = field(default_factory=dict)
    staves: dict[InstrumentPosition, list[Note]] = field(default_factory=dict)
    prev: "Beat" = field(default=None, repr=False)
    next: "Beat" = field(default=None, repr=False)
    goto: dict[PASS, "Beat"] = field(default_factory=dict)
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
        return self.bpm_start.get(self._pass_, self.bpm_start.get(ALL_PASSES, None))

    def get_bpm_end(self):
        return self.bpm_end.get(self._pass_, self.bpm_end.get(ALL_PASSES, None))

    def get_bpm_end_last_pass(self):
        return self.bpm_end.get(self._pass_, self.bpm_end.get(ALL_PASSES, None))

    def get_changed_tempo(self, current_tempo: BPM) -> BPM | None:
        tempo_change = self.tempo_changes.get(self._pass_, self.tempo_changes.get(ALL_PASSES, None))
        if tempo_change and tempo_change.new_tempo != current_tempo:
            if tempo_change.incremental:
                return current_tempo + int((tempo_change.new_tempo - current_tempo) / tempo_change.steps)
            else:
                return tempo_change.new_tempo
        return None


@dataclass
class Source:
    datapath: str
    infilename: str
    outfilefmt: str  # should contain 'position', 'ext' and 'midiversion' arguments
    font: NotationFont
    instrumentgroup: InstrumentGroup


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
    kempli: MetaDataStatus = MetaDataStatus.ON
    metadata: list[MetaData] = field(default_factory=list)


@dataclass
class FlowInfo:
    # Keeps track of statements that modify the sequence of
    # gongans or beats in the score. The main purpose of this
    # class is to keep track of gotos that point to labels that
    # have not yet been encountered while processing the score.
    labels: dict[str, Beat] = field(default_factory=dict)
    gotos: dict[str, tuple[Gongan, GoToMeta]] = field(default_factory=lambda: defaultdict(list))


@dataclass
class Score:
    source: Source
    midi_version: MidiVersion
    midi_version: MidiVersion
    instrumentgroup: InstrumentGroup = None
    instrument_positions: set[InstrumentPosition] = None
    gongans: list[Gongan] = field(default_factory=list)
    balimusic_font_dict: dict[str, Note] = None
    midi_notes_dict: dict[tuple[InstrumentPosition, Pitch, Octave, Stroke], MidiNote] = None
    position_range_lookup: dict[InstrumentPosition, tuple[Pitch, Octave, Stroke]] = None
    flowinfo: FlowInfo = field(default_factory=FlowInfo)
