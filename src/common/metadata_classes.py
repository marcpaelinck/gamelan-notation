from dataclasses import field
from typing import Literal, Optional, Union

from pydantic import BaseModel, Field

from src.common.constants import ALL_PASSES, PASS, NotationEnum


# MetaData related constants
class MetaDataStatus(NotationEnum):
    OFF = "off"
    ON = "on"


class GonganType(NotationEnum):
    REGULAR = "regular"
    KEBYAR = "kebyar"
    GINEMAN = "gineman"


class ValidationProperty(NotationEnum):
    BEAT_DURATION = "beat-duration"
    STAVE_LENGTH = "stave-length"
    INSTRUMENT_RANGE = "instrument-range"
    KEMPYUNG = "kempyung"


class MetaDataType(BaseModel):
    type: Literal[""]
    _processingorder_ = 99


class TempoMeta(MetaDataType):
    type: Literal["tempo"]
    bpm: int
    passes: list[PASS] = field(default_factory=list)
    first_beat: Optional[int] = 1
    beats: Optional[int] = 0
    passes: Optional[list[int]] = field(
        default_factory=lambda: list([ALL_PASSES])
    )  # On which pass(es) should goto be performed?
    passes: Optional[list[int]] = field(
        default_factory=lambda: list([ALL_PASSES])
    )  # On which pass(es) should goto be performed?

    @property
    def first_beat_seq(self) -> int:
        # Returns the pythonic sequence id (numbered from 0)
        return self.first_beat - 1


class LabelMeta(MetaDataType):
    type: Literal["label"]
    name: str
    beat: Optional[int] = 1
    _processingorder_ = 1

    @property
    def beat_seq(self) -> int:
        # Returns the pythonic sequence id (numbered from 0)
        return self.beat - 1


class GoToMeta(MetaDataType):
    type: Literal["goto"]
    label: str
    from_beat: Optional[int] | None = None  # Beat number from which to goto. Default is last beat of the gongan.
    passes: Optional[list[int]] = field(default_factory=list)  # On which pass(es) should goto be performed?

    @property
    def beat_seq(self) -> int:
        # Returns the pythonic sequence id (numbered from 0)
        return self.from_beat - 1 if self.from_beat else -1


class KempliMeta(MetaDataType):
    type: Literal["kempli"]
    status: MetaDataStatus


class GonganMeta(MetaDataType):
    type: Literal["gongan"]
    kind: GonganType


class ValidationMeta(MetaDataType):
    type: Literal["validation"]
    beats: Optional[list[int]] = field(default_factory=list)
    ignore: list[ValidationProperty]


MetaDataType = Union[TempoMeta, LabelMeta, GoToMeta, KempliMeta, GonganMeta, ValidationMeta]


class MetaData(BaseModel):
    data: MetaDataType = Field(..., discriminator="type")
