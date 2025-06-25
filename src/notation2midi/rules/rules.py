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
from typing import Any, ClassVar, override

from pydantic import BaseModel, Field

from src.common.constants import (
    InstrumentGroup,
    InstrumentType,
    Position,
    RuleParameter,
    RuleType,
    RuleValue,
)
from src.common.notes import Tone
from src.notation2midi.metadata_classes import MetaData
from src.notation2midi.rules.rule_cast_to_position import RuleCastToPosition
from src.notation2midi.rules.rule_parse_modifiers import RuleParseModifiers
from src.notation2midi.rules.rule_set_gracenote_octave import RuleSetGracenoteOctave
from src.settings.classes import RunSettings
from src.settings.constants import InstrumentFields, RuleFields
from src.settings.settings import RunSettingsListener


@dataclass(frozen=True)
class RuleDefinition:
    ruletype: RuleType
    positions: Position
    parameters: dict[RuleParameter, Any]


class Instrument(BaseModel, RunSettingsListener):

    group: InstrumentGroup
    positions: list[Position]
    instrumenttype: InstrumentType
    position_ranges: dict[Position, list[Tone]] = Field(default_factory=lambda: defaultdict(list))
    extended_position_ranges: dict[Position, list[Tone]] = Field(default_factory=lambda: defaultdict(list))
    instrument_range: list[Tone] = Field(default_factory=list)

    def merge(self, other: "Instrument") -> "Instrument":
        """
        Merge the data of another Instrument object into this one.

        If the other Instrument is None, returns self unchanged. Otherwise, combines the positions, position ranges,
        extended position ranges, and instrument ranges of both Instrument objects. The instrument_range is merged,
        duplicates are removed, and the result is sorted by the 'key' attribute.

        Args:
            other (Instrument): Another Instrument object to merge with this one.

        Returns:
            Instrument: The updated Instrument object with merged data.
        """
        if not other:
            return self
        # Merge the data of two Instrument objects.
        self.positions += other.positions  # pylint: disable=no-member; -> incorrect warning
        self.position_ranges = self.position_ranges | other.position_ranges
        self.extended_position_ranges = self.extended_position_ranges | other.extended_position_ranges
        self.instrument_range = sorted(list(set(self.instrument_range + other.instrument_range)), key=lambda x: x.key)
        return self


class Rule(RunSettingsListener):
    _RANGE: dict[Position, list[Tone]]  # default tone range per position (e.g. reyong1: deng0..dang0)
    _EXTENDED_RANGE: dict[Position, list[Tone]]  # max tone range per position (e.g. reyong1: deng0..dong1)
    _MAX_RANGE: list[Tone]  # all possible tones for the entire orchestra
    _RULEDEFS: dict[Position, dict[RuleType, list[RuleDefinition]]]  # Rules in the instrument config section

    def __init__(self, run_settings: RunSettings):
        self.run_settings = run_settings

    # pylint: disable=unused-argument
    def fire(
        self, notes: list[Any], position: Position, all_positions: list[Position], metadata: list[MetaData]
    ) -> Any: ...

    # pylint: enable=unused-argument

    @classmethod
    @override
    def cls_initialize(cls, run_settings: RunSettings):
        cls._init_pos_ranges(run_settings)
        cls._init_ruledefs(run_settings)

    @classmethod
    def _init_pos_ranges(cls, run_settings: RunSettings):
        """Populates the class's range dicts and lists."""
        all_tones = set()

        for row in run_settings.data.instruments:
            if (InstrumentGroup[row["group"]]) != run_settings.instrumentgroup:
                continue
            # Create an Instrument object for the current data record, which contains data for a single
            # instrument position.
            cls._RANGE[row[InstrumentFields.POSITION]] = sorted(row[InstrumentFields.PITCHES], key=lambda x: x.key)
            cls._EXTENDED_RANGE[row[InstrumentFields.POSITION]] = sorted(
                row[InstrumentFields.PITCHES] + row[InstrumentFields.EXTENDED_PITCHES],
                key=lambda x: x.key,
            )
            all_tones.update(set(cls._EXTENDED_RANGE[row[InstrumentFields.POSITION]]))

        cls._MAX_RANGE = sorted(list(all_tones), key=lambda x: x.key)

    @classmethod
    def _init_ruledefs(cls, run_settings: RunSettings):
        """Populates the _RULEDEFS dict."""
        cls._RULES = defaultdict(lambda: defaultdict(list))
        for row in run_settings.data.rules:
            if (InstrumentGroup[row["group"]]) != run_settings.instrumentgroup:
                continue
            # Create an Instrument object for the current data record, which contains data for a single
            # instrument position.
            record = row.copy()
            for position in (
                Position
                # [pos for pos in Position if not cls._RULES[pos]]
                if record["positions"] == RuleValue.ANY
                else record["positions"]
            ):
                # Replace a generic rule (= valid for any position) with a specific one.
                rulelist: list[RuleDefinition] = cls._RULES[position][record[RuleFields.RULETYPE]]
                ruletype = record[RuleFields.RULETYPE]
                generic_rule = next(
                    (r for r in rulelist if r.ruletype == ruletype and r.positions == RuleValue.ANY),
                    None,
                )
                if generic_rule:
                    rulelist.remove(generic_rule)
                rulelist.append(
                    RuleDefinition(
                        ruletype=record[RuleFields.RULETYPE],
                        positions=record[RuleFields.POSITIONS],
                        parameters={
                            record[parm]: record[val]
                            for parm, val in [
                                (RuleFields.PARAMETER1, RuleFields.VALUE1),
                                (RuleFields.PARAMETER2, RuleFields.VALUE2),
                            ]
                            if record[parm]
                        },
                    )
                )


class RulesEngine(BaseModel, RunSettingsListener):
    _RULES: ClassVar[list[Rule]] = [RuleParseModifiers, RuleCastToPosition, RuleSetGracenoteOctave]
