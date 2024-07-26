import inspect
from collections import defaultdict
from dataclasses import dataclass, field
from enum import Enum
from typing import Literal, Optional, Union

from eth_pydantic_types import HexBytes
from pydantic import BaseModel, Field, computed_field, field_validator, model_validator

from notation_constants import (
    BPM,
    DEFAULT,
    INSTRUMENT,
    PASS,
    InstrumentGroup,
    InstrumentType,
    SymbolValue,
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


# Notation to MIDI


class Character(BaseModel):
    symbol: str
    unicode: str
    symbol_description: str
    balifont_symbol_description: str
    meaning: SymbolValue
    duration: float
    rest_after: float
    description: str


class MidiNote(BaseModel):
    instrumentgroup: InstrumentGroup
    instrumenttype: InstrumentType
    notevalue: SymbolValue
    midi: int
    pianomidi: Optional[int] = -1


#
# Metadata
#
class Tempo(BaseModel):
    type: Literal["tempo"]
    bpm: int
    passes: list[PASS] = field(default_factory=list)
    first_beat: Optional[int] = 1
    beats: Optional[int] = 0
    passes: Optional[list[int]] = field(default_factory=list)  # On which pass(es) should goto be performed?

    @computed_field
    @property
    def first_beat_seq(self) -> int:
        # Returns the pythonic sequence id (numbered from 0)
        return self.first_beat - 1

    @model_validator(mode="after")
    def set_default_pass(self):
        if not self.passes:
            self.passes.append(DEFAULT)
        return self


class Label(BaseModel):
    type: Literal["label"]
    label: str
    beat_nr: Optional[int] = 1

    @computed_field
    @property
    def beat_seq(self) -> int:
        # Returns the pythonic sequence id (numbered from 0)
        return self.beat_nr - 1


class GoTo(BaseModel):
    type: Literal["goto"]
    label: str
    beat_nr: Optional[int] | None = None  # Beat number from which to goto. Default is last beat of the system.
    passes: Optional[list[int]] = field(default_factory=list)  # On which pass(es) should goto be performed?

    @computed_field
    @property
    def beat_seq(self) -> int:
        # Returns the pythonic sequence id (numbered from 0)
        return self.beat_nr - 1 if self.beat_nr else -1


class Gongan(BaseModel):
    type: Literal["gongan"]
    kind: str


class MetaData(BaseModel):
    data: Union[Tempo, Label, GoTo, Gongan] = Field(..., discriminator="type")


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
    staves: dict[INSTRUMENT, list[Character]] = field(default_factory=dict)
    next: "Beat" = field(default=None, repr=False)
    goto: dict[PASS, "Beat"] = field(default_factory=dict)
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

    def get_bpm_start(self):
        return self.bpm_start.get(self._pass_, self.bpm_start.get(DEFAULT, None))

    def get_bpm_end(self):
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
class System:
    # A set of beats.
    # A System will usually span one gongan.
    id: int
    beats: list[Beat] = field(default_factory=list)
    beat_duration: int = 4
    gongan: Gongan = field(default_factory=lambda: Gongan(type="gongan", kind="regular"))


@dataclass
class Score:
    title: str
    instruments: set[Instrument]
    systems: list[System] = field(default_factory=list)


@dataclass
class FlowInfo:
    labels: dict[str, Beat] = field(default_factory=dict)
    gotos: dict[str, tuple[System, GoTo]] = field(default_factory=lambda: defaultdict(list))
