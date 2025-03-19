"""Contains record-like data classes that are used to store the parsed results.
These records will be parsed to the final object model in the dict_to_score step.
This way, the parsing logic and the object model logic can be applied separately
which makes the code easier to understand and to maintain.
"""

from dataclasses import dataclass, fields

from src.common.constants import InstrumentType, Modifier, Pitch, Position, Stroke
from src.common.metadata_classes import (
    FrequencyType,
    GonganType,
    MetaDataSwitch,
    Scope,
    ValidationProperty,
)

# pylint: disable=missing-class-docstring
# pylint: disable=too-many-instance-attributes


@dataclass(frozen=True, kw_only=False)
class NoteRecord:
    symbol: str
    pitch: Pitch
    octave: int
    stroke: Stroke
    duration: float
    rest_after: float
    modifier: Modifier | None = Modifier.NONE

    @classmethod
    def fieldnames(cls) -> list[str]:
        """Returns the field names"""
        return [f.name for f in fields(cls)]


@dataclass(frozen=True, kw_only=False)
class MetaDataRecord:
    abbreviation: str = None
    beat: int | None = None
    beat_count: int | None = None
    beats: list[int] | None = None
    count: int = None
    first_beat: int | None = None
    frequency: FrequencyType = None
    from_beat: int | None = None
    ignore: list[ValidationProperty] = None
    instrument: InstrumentType = None
    label: str = None
    line: int = None
    metatype: None = None
    name: str = None
    octaves: int = None
    passes: list[int] | None = None
    positions: list[Position] = None
    scope: Scope | None = None
    status: MetaDataSwitch = None
    type: GonganType = None
    value: int | list[str] | None = None

    @classmethod
    def fieldnames(cls) -> list[str]:
        """Returns the field names"""
        return [f.name for f in fields(cls)]
