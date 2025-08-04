"""Contains logic about the instruments in relation to the notation.
Examples of logic are:
- The range of each instrument
- Determine how to assign notes to each instrument when (a part of) the
  notation applies to a group of instruments that have different ranges.
- Transpositions such as kempyung.
- Shortcut notation such as norot.
"""

from collections import defaultdict
from dataclasses import dataclass
from enum import StrEnum
from typing import Any, ClassVar, override

from pydantic import BaseModel

from src.common.classes import Measure
from src.common.constants import (
    InstrumentType,
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


class ToneRange(StrEnum):
    """Types of ranges of melodic tones"""

    REGULAR = "REGULAR"  # e.g. DENG0...DANG0 for gong kebyar REYONG_1.
    EXTENDED = "EXTENDED"  # e.g. DENG0...DONG1 for gong kebyar REYONG_1.
    INSTRUMENT = "INSTRUMENT"  # e.g. DENG0..DUNG2 for gong kebyar reyong.
    GROUP = "GROUP"  # e.g. DONG0..DANG2 for gong kebyar orchestra.


@dataclass(frozen=True)
class RuleDefinition:
    ruletype: RuleType
    positions: Position
    conditions: dict[RuleCondition, Any]
    action: dict[RuleAction, Any]


class Instrument(BaseModel, RunSettingsListener):
    """This class contains information about the range of melodic tones for each position and instrument.
    The information is used to determine the correct pitch and octave when casting tones to specific positions."""

    DEFAULT_RANGE: ClassVar[dict] = {}
    MAX_RANGE: ClassVar[dict] = {}
    ORCHESTRA_RANGE: ClassVar[list] = []
    POS_PER_INSTRUMENT_TYPE: ClassVar[dict] = {}

    @classmethod
    def _init_pos_ranges(cls, run_settings: RunSettings):
        """Populates the class's range dicts and lists."""
        all_tones = set()
        cls.DEFAULT_RANGE = {}
        cls.MAX_RANGE = {}
        cls.POS_PER_INSTRUMENT_TYPE = defaultdict(set)
        for row in run_settings.data.instruments.filterOn(run_settings.instrumentgroup):
            # Create an Instrument object for the current data record, which contains data for a single
            # instrument position.
            cls.POS_PER_INSTRUMENT_TYPE[row[InstrumentFields.INSTRUMENTTYPE]].add(row[InstrumentFields.POSITION])
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
    def get_instrumenttype(cls, position: Position) -> InstrumentType:
        return next((itype for itype, positions in cls.POS_PER_INSTRUMENT_TYPE.items() if position in positions), None)

    @classmethod
    def get_range(cls, position: Position, tonerange: ToneRange) -> list[Tone]:
        match (tonerange):
            case ToneRange.REGULAR:
                return cls.DEFAULT_RANGE[position]
            case ToneRange.EXTENDED:
                return cls.MAX_RANGE[position]
            case ToneRange.INSTRUMENT:
                instrument_type = cls.get_instrumenttype(position)
                all_pos = cls.POS_PER_INSTRUMENT_TYPE[instrument_type]
                # Combine the ranges of all the instrument's positions and remove duplicates.
                all_tones = list(set(sum((cls.MAX_RANGE[pos] for pos in all_pos), [])))
                return sorted(all_tones, key=lambda x: x.key)
            case ToneRange.GROUP:
                # Combine the ranges of all the group's positions and remove duplicates.
                all_tones = list(set(sum((cls.MAX_RANGE.values()), [])))
                return sorted(all_tones, key=lambda x: x.key)
            case _:
                raise ValueError("Unexpected tone range type %s" % tonerange)

    @classmethod
    def get_tones_sorted_by_distance(
        cls, tone: Tone, position: Position, tonerange: ToneRange = ToneRange.REGULAR, match_octave=False
    ) -> list[Tone]:
        """Returns the required range, sorted by absolute distance to tone.octave in sequence 0, +1, -1, +2, -2"""
        tones_in_range = cls.get_range(position, tonerange=tonerange)
        return sorted(
            [t for t in tones_in_range if t.pitch == tone.pitch and (t.octave == tone.octave or not match_octave)],
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
