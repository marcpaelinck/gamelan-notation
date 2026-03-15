import json
from collections import defaultdict
from typing import ClassVar, DefaultDict, Union

from pydantic import BaseModel, Field, RootModel, field_serializer

from src.common.constants import Position
from src.notationparser.json.compact_encoder import Compact


class GonganInfo(BaseModel):
    id: int


class BeatInfo(BaseModel):
    UPDATEFREQ: ClassVar[int] = 24
    fullid: str
    duration: float
    start_bpm: int
    end_bpm: int
    start_velocities: dict[Position, int]
    end_velocities: dict[Position, int]


def roundoff(value: float) -> float | int:
    # Rounds off with as little decimals as possible without loss, but with a maximum of 3
    rounded = 0
    rounded3 = round(value, 3)
    for decimals in range(4):
        rounded = round(value, decimals)
        if int(rounded * pow(10, decimals)) == rounded3 * pow(10, decimals):
            break
    return int(rounded) if decimals == 0 else rounded


UUID = str


# Base class
class ExecutionItemBase(BaseModel):
    type: str
    seqId: int | None  # Sequence in the list of Execution items. Used by the item editor.
    passes: list[int] | None  # Pass ints for which the item applies
    nthpass: bool | None  # undefined: no condition. false: item applies to listed passes only.
    #  true: item applies to every nth pass (n in passes list), e.g. every 3rd & 4th pass.
    tooltip: str
    tooltipshort: str


# Enables to deviate form the default playing sequence: indicates the next System.
class GotoItem(ExecutionItemBase):
    type: str = "goto"
    targetuuid: UUID  # next System to play.
    targetname: str  # Display name of the target System.


# Enables to repeat the current System.
class LoopItem(ExecutionItemBase):
    type: str = "loop"
    count: int  # Total int of times to play the System consecutively.


class ExpressionItemBase(ExecutionItemBase):
    type: str
    loops: list[int] | None  # In case the System has a LoopItem, specifies for which iterations the expression applies.
    isGradual: bool | None  # True: the expression value should increase / decrease over one or more Section.
    fromSection: (
        int | None
    )  # If isGradual==true: Gradual change starts at the beginning of this Section. Otherwise undefined.
    toSection: int  # If isGradual==true: the gradual change should continue until the end of this section.
    # Otherwise the gradual change should be effective immediately at the start of this section.
    fromValue: float | None  # If isGradual==true: starting value of the gradual change. Otherwise undefined.
    toValue: float  # If isGradual==true: end value of the gradual change. Otherwise: new immediate value.


class TempoItem(ExpressionItemBase):
    type: str = "tempo"


class DynamicsItem(ExpressionItemBase):
    type: str = "dynamics"
    fromDynamics: str | None  # If isGradual==true: starting value for gradual change. Otherwise undefined.
    toDynamics: str  # If isGradual==true: end value of the gradual change. Otherwise: new immediate value.
    positions: list[str]


ExecutionItem = Union[GotoItem, LoopItem, TempoItem, DynamicsItem]


class Measure(BaseModel):
    notation: list[str] = Field(default_factory=list)


# Used in serialization
Staff = RootModel[list[Measure]]


# Subdivision of a score, typically spans one gongan
class System(BaseModel):
    uuid: UUID  # unique uuid, never changes
    id: int  # system id as shown to user, starts with 1, can change when data items are  added / deleted
    index: int  # row index, starts with 0, can change when data items are added / deleted
    label: str | None = None
    execution: list[ExecutionItem] | None = None
    staffs: dict[Position, Staff] = Field(
        default_factory=dict
    )  # Contains the notation as a sequence of measures for each position.
    colWidths: list[int] | None = None
    loop: LoopItem | None = None
    copyfrom: str | None = None  # label or id of copied system
    copyfromkey: UUID | None = None  # uuid copied system
    grouped: list[str] = (
        []
    )  # positions that are/were grouped in the editor for simultaneous editing using casting rules.

    @field_serializer("staffs", when_used="always")
    def serialize_staffs(self, data: dict[Position, list[Measure]]):
        return {pos: Compact(staff.model_dump(exclude_defaults=True)) for pos, staff in data.items()}

    @field_serializer("execution", when_used="always")
    def serialize_execution(self, data: list[ExecutionItem]):
        return [Compact(exec.model_dump(exclude_none=True)) for exec in data]

    @field_serializer("colWidths", when_used="always")
    def serialize_colwidths(self, data: list[int]):
        return Compact(data)


class Score(BaseModel):
    uuid: UUID
    title: str
    composer: str
    instrumenttype: str
    positions: list[Position] = Field(default_factory=list)
    parts: DefaultDict[str, list[UUID]] = Field(default_factory=lambda: defaultdict(list))
    systems: list[System] = Field(default_factory=list)
