"""Contains logic about the instruments in relation to the notation.
Examples of logic are:
- The range of each instrument
- Determine how to assign notes to each instrument when (a part of) the
  notation applies to a group of instruments that have different ranges.
- Transpositions such as kempyung.
- Shortcut notation such as norot.
"""

import math
from collections import defaultdict
from typing import ClassVar, override

from pydantic import BaseModel, Field

from src.common.constants import (
    InstrumentGroup,
    InstrumentType,
    NotationEnum,
    Pitch,
    Position,
    RuleParameter,
    RuleType,
    RuleValue,
)
from src.common.notes import Rule, Tone
from src.notation2midi.metadata_classes import (
    AutoKempyungMeta,
    MetaData,
    MetaDataSwitch,
)
from src.settings.classes import RunSettings
from src.settings.constants import InstrumentFields, RuleFields
from src.settings.settings import RunSettingsListener


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


class RulesEngine(BaseModel, RunSettingsListener):
    _POS_TO_INSTR: ClassVar[dict[Position, Instrument]]
    _RULES: ClassVar[dict[Position, dict[RuleType, list[Rule]]]]
    _MAX_RANGE: list[Tone]

    @classmethod
    @override
    def cls_initialize(cls, run_settings: RunSettings):
        cls._init_pos_to_instr(run_settings)
        cls._init_rules(run_settings)

    @classmethod
    def get_instrument(cls, position: Position) -> Instrument:
        return cls._POS_TO_INSTR[position]

    @classmethod
    def get_range(cls, position: Position, extended: bool = False) -> list[Tone]:
        return (
            cls._POS_TO_INSTR[position].extended_position_ranges[position]
            if extended
            else cls._POS_TO_INSTR[position].position_ranges[position]
        )

    @classmethod
    def get_tones_within_range(
        cls, tone: Tone, position: Position, extended_range: bool = False, match_octave=False
    ) -> list[Tone]:
        # The list is sorted by absolute distance to tone.octave in sequence 0, +1, -1, +2, -2
        return sorted(
            [
                t
                for t in RulesEngine.get_range(position, extended=extended_range)
                if t.pitch == tone.pitch and (t.octave == tone.octave or not match_octave)
            ],
            key=lambda x: abs(x.octave - tone.octave - 0.1),
        )

    @classmethod
    def interval(cls, tone1: Tone, tone2: Tone) -> int:
        """Returns the difference between the indices of the tones in their natural sorting order.

        Args:
            tone1 (Tone): _description_
            tone2 (Tone): _description_

        Raises:
            Exception: if either tone is not within the instrument group's range.

        Returns:
            int: the interval
        """
        if not (tone1 in cls._MAX_RANGE and tone2 in cls._MAX_RANGE):
            raise ValueError(f"{tone1} and/or {tone2} not within the orchestra's range.")
        return cls._MAX_RANGE.index(tone2) - cls._MAX_RANGE.index(tone1)

    @classmethod
    def get_kempyung_pitch(cls, position, pitch: Pitch, inverse: bool = False) -> Pitch | None:
        return next(
            (
                (p if inverse else k)
                for p, k in cls._RULES[position][RuleType.KEMPYUNG][0].parameters[RuleParameter.NOTE_PAIRS]
                if (k if inverse else p) is pitch
            ),
            None,
        )

    @classmethod
    def get_kempyung_tones_within_range(
        cls, tone: Tone, position, extended_range: bool = False, exact_octave_match: bool = True, inverse: bool = False
    ) -> list[Tone]:
        """Returns all the tones with the kempyung pitch of the given tone and which lie in
        the position's range.

        Args:
            tone (Tone): reference tone.
            position (_type_): position which determines the range.
            extended_range (bool, optional): if True, the extended range should be used, otherwise the 'regular' range. Defaults to False.
            exact_octave_match (bool, optional): If True, returns only the tone that lies within an octave above the reference note. Defaults to True.
            inverse (bool, optional): Return the inverse kempyung (the tone for which the given tone is a kempyung tone)

        Returns:
            list[Tone]: a list of kempyung tones or an empty list if none found.
        """
        kempyung_pitch = cls.get_kempyung_pitch(position, tone.pitch, inverse)
        # List possible octaves, looking at octaves equal or highter than the reference tone first
        try_octaves = [tone.octave, tone.octave + 1, tone.octave + 2, tone.octave - 1, tone.octave - 2]
        oct_interval = RulesEngine.interval(Tone(pitch=Pitch.DONG, octave=0), Tone(pitch=Pitch.DONG, octave=1))
        inv = -1 if inverse else 1
        k_list = [
            Tone(pitch=kempyung_pitch, octave=octave)
            for octave in try_octaves
            if Tone(pitch=kempyung_pitch, octave=octave) in RulesEngine.get_range(position, extended_range)
            and (
                not exact_octave_match
                or 0 < inv * RulesEngine.interval(tone, Tone(pitch=kempyung_pitch, octave=octave)) < oct_interval
            )
        ]
        # Put kempyung tones that are higher than the reference tone first.
        return sorted(
            k_list, key=lambda x: [0, 1, 2, -1, -2].index(math.floor(RulesEngine.interval(tone, x) / oct_interval))
        )

    @classmethod
    def get_shared_notation_rule(cls, position: Position, unisono_positions: set[Position]) -> Rule:
        rules = cls._RULES.get(position, {}).get(
            RuleType.UNISONO, None
        )  # or cls._RULES.get(RuleValue.ANY, {}).get(RuleType.SHARED_NOTATION, None)
        if rules:
            rule = next(
                (rule for rule in rules if set(rule.parameters[RuleParameter.SHARED_BY]) == set(unisono_positions)),
                None,
            ) or next((rule for rule in rules if rule.parameters[RuleParameter.SHARED_BY] == RuleValue.ANY), None)
            if rule:
                return rule.parameters[RuleParameter.TRANSFORM]
        return None

    @classmethod
    def cast_to_position(
        cls, tone: Tone, position: Position, all_positions: set[Position], metadata: list[MetaData]
    ) -> Tone | None:
        """Returns the equivalent tone for `position`, given that the same notation is common for `all_positions`.
        This method uses instrument rules that describe how to interpret a common notation line for multiple
        positions.

        Args:
            tone (Tone): original 'unisono' tone parsed from the notation.
            position (Position): position for which the rule should apply.
            all_positions (set[Position]): positions that share the same notation.

        Raises:
            Exception: no unisono rule found for the position.

        Returns:
            Tone | None: the tone, cast to the position.
        """
        # Select metadata that affects the rules
        autokempyung = True
        for meta in metadata:
            if (
                isinstance(meta, AutoKempyungMeta)
                and meta.status == MetaDataSwitch.OFF
                and (not meta.positions or position in meta.positions)
            ):
                autokempyung = False

        # Rules only apply to melodic pitches.
        if not tone.is_melodic():
            return tone

        rule = RulesEngine.get_shared_notation_rule(position, set(all_positions))
        if not rule:
            raise ValueError(f"No unisono rule found for {position}.")

        for action in rule:
            match action:
                case RuleValue.SAME_TONE:
                    # retain pitch and octave
                    tones = cls.get_tones_within_range(tone, position, extended_range=False, match_octave=True)
                case RuleValue.SAME_PITCH:
                    # retain pitch, select octave within instrument's range
                    tones = cls.get_tones_within_range(tone, position, extended_range=False, match_octave=False)
                case RuleValue.SAME_PITCH_EXTENDED_RANGE:
                    # retain pitch, select octave within instrument's extended range
                    tones = cls.get_tones_within_range(tone, position, extended_range=True, match_octave=False)
                case RuleValue.EXACT_KEMPYUNG:
                    if autokempyung:
                        # select kempyung tone that lies immediately above the given tone
                        tones = cls.get_kempyung_tones_within_range(
                            tone, position, extended_range=False, exact_octave_match=True
                        )
                    else:
                        tones = cls.get_tones_within_range(
                            tone, position, extended_range=False, match_octave=True
                        ) or cls.get_tones_within_range(tone, position, extended_range=False, match_octave=False)
                case RuleValue.KEMPYUNG:
                    if autokempyung:
                        # select kempyung pitch that lies within instrument's range
                        tones = cls.get_kempyung_tones_within_range(
                            tone, position, extended_range=False, exact_octave_match=False
                        )
                    else:
                        tones = cls.get_tones_within_range(
                            tone, position, extended_range=False, match_octave=True
                        ) or cls.get_tones_within_range(tone, position, extended_range=False, match_octave=False)
            if tones:
                return Tone(pitch=tones[0].pitch, octave=tones[0].octave, transformation=action)

        return None

    @classmethod
    def _parse_range(cls, note_range: str) -> list[Tone]:
        return sorted(
            [Tone(*t) for t in note_range],
            key=lambda x: x.key,
        )

    @staticmethod
    def _get_member_map(classes: list[NotationEnum]) -> dict[str, NotationEnum]:
        """Creates a mapping {value -> object} for the members of all NotationEnum subclasses.
        Args:
            classes (list[NotationEnum]): List of enum classes
        Returns:
            _type_: _description_
        """
        return {m.name: m for cls in classes for m in cls}

    @classmethod
    def _init_pos_to_instr(cls, run_settings: RunSettings):
        """Creates the _POS_TO_INSTR lookup dict."""
        # Field definition
        # pylint: disable=invalid-name
        POSITIONS = InstrumentFields.POSITION + "s"
        POSITION_RANGES = InstrumentFields.POSITION_RANGE + "s"
        EXTENDED_POSITION_RANGES = InstrumentFields.EXTENDED_POSITION_RANGE + "s"
        INSTRUMENT_RANGE = "INSTRUMENT_RANGE"
        # pylint: enable=invalid-name

        # First create a dict with all instruments to merge multiple data records for the same instrument type.
        instr_dict: dict[InstrumentType, Instrument] = defaultdict(lambda: None)
        all_tones = set()

        for row in run_settings.data.instruments:
            if (InstrumentGroup[row["group"]]) != run_settings.instrumentgroup:
                continue
            # Create an Instrument object for the current data record, which contains data for a single
            # instrument position.
            record = row.copy()
            record[POSITIONS] = [position := record[InstrumentFields.POSITION]]
            record[POSITION_RANGES] = {
                position: [
                    Tone(**dict(zip(("pitch", "octave"), tpl))) for tpl in record[InstrumentFields.POSITION_RANGE]
                ]
            }
            record[EXTENDED_POSITION_RANGES] = {
                position: [
                    Tone(**dict(zip(("pitch", "octave"), tpl)))
                    for tpl in record[InstrumentFields.EXTENDED_POSITION_RANGE]
                ]
                or record[POSITION_RANGES][position]
            }
            record[INSTRUMENT_RANGE] = record[EXTENDED_POSITION_RANGES][position]

            all_tones.update(set(record[INSTRUMENT_RANGE]))
            instrument = Instrument.model_validate(record)
            instr_dict[instrument.instrumenttype] = instrument.merge(instr_dict[instrument.instrumenttype])

        # Invert the dict
        cls._POS_TO_INSTR = {pos: instr for instr in instr_dict.values() for pos in instr.positions}
        cls._MAX_RANGE = sorted(list(all_tones), key=lambda x: x.key)

    @classmethod
    def _init_rules(cls, run_settings: RunSettings):
        """Creates the _RULES_DICT."""
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
                rulelist: list[Rule] = cls._RULES[position][record[RuleFields.RULETYPE]]
                ruletype = record[RuleFields.RULETYPE]
                generic_rule = next(
                    (r for r in rulelist if r.ruletype == ruletype and r.positions == RuleValue.ANY),
                    None,
                )
                if generic_rule:
                    rulelist.remove(generic_rule)
                rulelist.append(
                    Rule(
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
