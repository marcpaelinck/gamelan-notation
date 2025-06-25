import math

from src.common.constants import Pitch, Position, RuleParameter, RuleType, RuleValue
from src.common.notes import Tone
from src.notation2midi.metadata_classes import (
    AutoKempyungMeta,
    MetaData,
    MetaDataSwitch,
)
from src.notation2midi.rules.rules import Rule, RuleDefinition


class RuleCastToPosition(Rule):
    @classmethod
    def get_range(cls, position: Position, extended: bool = False) -> list[Tone]:
        return cls._EXTENDED_RANGE[position] if extended else cls._RANGE[position]

    # TODO move to separate utils class
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
        oct_interval = cls.interval(Tone(pitch=Pitch.DONG, octave=0), Tone(pitch=Pitch.DONG, octave=1))
        inv = -1 if inverse else 1
        k_list = [
            Tone(pitch=kempyung_pitch, octave=octave)
            for octave in try_octaves
            if Tone(pitch=kempyung_pitch, octave=octave) in cls.get_range(position, extended_range)
            and (
                not exact_octave_match
                or 0 < inv * cls.interval(tone, Tone(pitch=kempyung_pitch, octave=octave)) < oct_interval
            )
        ]
        # Put kempyung tones that are higher than the reference tone first.
        return sorted(k_list, key=lambda x: [0, 1, 2, -1, -2].index(math.floor(cls.interval(tone, x) / oct_interval)))

    @classmethod
    def get_shared_notation_rule(cls, position: Position, unisono_positions: set[Position]) -> RuleDefinition:
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
        if not all_positions:
            raise ValueError("Trying to cast a note to %s but position group is empty." % all_positions)
        elif position not in all_positions:
            raise ValueError("Trying to cast a note to %s which is not in %s." % (position, all_positions))

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

        rule = (
            RuleValue.SAME_TONE
            if len(all_positions) == 1
            else cls.get_shared_notation_rule(position, set(all_positions))
        )
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
