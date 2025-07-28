"""Contains logic about the instruments in relation to the notation.
Examples of logic are:
- The range of each instrument
- Determine how to assign notes to each instrument when (a part of) the
  notation applies to a group of instruments that have different ranges.
- Transpositions such as kempyung.
- Shortcut notation such as norot.
"""

from dataclasses import dataclass
from typing import Any, ClassVar, override

from pydantic import BaseModel

from src.common.classes import Measure
from src.common.constants import (
    InstrumentGroup,
    Position,
    RuleAction,
    RuleCondition,
    RuleType,
)
from src.common.notes import Tone
from src.notation2midi.metadata_classes import MetaData
from src.settings.classes import RunSettings
from src.settings.constants import InstrumentFields
from src.settings.settings import RunSettingsListener


@dataclass(frozen=True)
class RuleDefinition:
    ruletype: RuleType
    positions: Position
    conditions: dict[RuleCondition, Any]
    action: dict[RuleAction, Any]


class Instrument(BaseModel, RunSettingsListener):
    DEFAULT_RANGE: ClassVar[dict] = {}
    MAX_RANGE: ClassVar[dict] = {}
    ORCHESTRA_RANGE: ClassVar[list] = []

    @classmethod
    def _init_pos_ranges(cls, run_settings: RunSettings):
        """Populates the class's range dicts and lists."""
        all_tones = set()
        cls.DEFAULT_RANGE = {}
        cls.MAX_RANGE = {}
        for row in run_settings.data.instruments.filterOn(run_settings.instrumentgroup):
            if (InstrumentGroup[row["group"]]) != run_settings.instrumentgroup:
                continue
            # Create an Instrument object for the current data record, which contains data for a single
            # instrument position.
            cls.DEFAULT_RANGE[row[InstrumentFields.POSITION]] = sorted(
                [Tone(pitch=pitch, octave=octave) for pitch, octave in row[InstrumentFields.TONES]],
                key=lambda tone: tone.key,
            )
            cls.MAX_RANGE[row[InstrumentFields.POSITION]] = sorted(
                [
                    Tone(pitch=pitch, octave=octave)
                    for pitch, octave in row[InstrumentFields.TONES] + row[InstrumentFields.EXTENDED_TONES]
                ],
                key=lambda x: x.key,
            )
            all_tones.update(set(cls.MAX_RANGE[row[InstrumentFields.POSITION]]))

        cls.ORCHESTRA_RANGE = sorted(list(all_tones), key=lambda x: x.key)

    @classmethod
    @override
    def cls_initialize(cls, run_settings: "RunSettings"):
        cls._init_pos_ranges(run_settings)

    @classmethod
    def get_range(cls, position: Position, extended: bool = False) -> list[Tone]:
        return cls.MAX_RANGE[position] if extended else Instrument.DEFAULT_RANGE[position]

    @classmethod
    def get_tones_within_range(
        cls, tone: Tone, position: Position, extended_range: bool = False, match_octave=False
    ) -> list[Tone]:
        # The list is sorted by absolute distance to tone.octave in sequence 0, +1, -1, +2, -2
        return sorted(
            [
                t
                for t in cls.get_range(position, extended=extended_range)
                if t.pitch == tone.pitch and (t.octave == tone.octave or not match_octave)
            ],
            key=lambda x: abs(x.octave - tone.octave - 0.1),
        )

    # TODO move to separate utils class

    @classmethod
    def interval(cls, tone1: Tone, tone2: Tone) -> int:
        """Returns the difference between the indices of the tones in their natural sorting order.

        Args:
            tone1 (Tone): lower tone
            tone2 (Tone): higher tone

        Raises:
            Exception: if either tone is not within the instrument group's range.

        Returns:
            int: the interval
        """
        if not (tone1 in cls.ORCHESTRA_RANGE and tone2 in cls.ORCHESTRA_RANGE):
            raise ValueError(f"{tone1} and/or {tone2} not within the orchestra's range.")
        return cls.ORCHESTRA_RANGE.index(tone2) - cls.ORCHESTRA_RANGE.index(tone1)


class Rule:

    NAME = "BASE RULE"  # replace in each subclassed rule

    def __init__(self, run_settings: RunSettings):
        self.run_settings = run_settings

    # pylint: disable=unused-argument
    def fire(
        self, pass_: Measure.Pass, position: Position, all_positions: list[Position], metadata: list[MetaData]
    ) -> None:
        return None

    # pylint: enable=unused-argument
