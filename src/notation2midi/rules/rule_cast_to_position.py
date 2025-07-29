import math
from collections import defaultdict
from typing import Any

from src.common.classes import Measure
from src.common.constants import (
    PatternType,
    Pitch,
    Position,
    RuleAction,
    RuleCondition,
    RuleType,
    RuleValue,
)
from src.common.notes import GenericNote, Note, NoteFactory, Pattern, Tone
from src.notation2midi.metadata_classes import MetaData, MetaDataSwitch, MetaType
from src.notation2midi.rules.rule import Instrument, Rule, RuleDefinition
from src.settings.classes import RunSettings
from src.settings.constants import ModifiersFields, RuleFields
from src.settings.settings import RunSettingsListener


class RuleCastToPosition(Rule, RunSettingsListener):
    """Converts all GenericNote instances (which are not bound to a specific instrument) to Note or Pattern instances.
    The latter two are bound to specific instruments, which means that they belong to the instrument's range.
    This class is used for staves that apply to multiple instruments. Each note's pitch and octave are inferred using
    the instrument rules given in the instrument config.
    """

    NAME = "Cast notes to instrument positions (converts GenericNote instances to Note and Pattern instances)"
    RULES = dict[Position, list[RuleDefinition]]

    @classmethod
    def cls_initialize(cls, run_settings: RunSettings):
        cls.MODIFIER_DICT = {
            row[ModifiersFields.MODIFIER]: (row[ModifiersFields.NOTE_ATTRIBUTE], row[ModifiersFields.VALUE])
            for row in run_settings.data.modifiers
        }
        cls.RULES = cls._init_ruledefs(run_settings)

    def fire(
        self, pass_: Measure.Pass, position: Position, all_positions: list[Position], metadata: list[MetaData]
    ) -> None:
        pass_.notes = self.to_bound_notes(
            notes=pass_.genericnotes, position=position, all_positions=all_positions, metadata=metadata
        )

    @classmethod
    def _init_ruledefs(cls, run_settings: RunSettings) -> dict[Position, dict[RuleType, Any]]:
        """create a rules dict."""
        ruledict = defaultdict(lambda: defaultdict(list))
        for row in run_settings.data.rules.filterOn(run_settings.instrumentgroup):
            # Create an Instrument object for the current data record, which contains data for a single
            # instrument position.
            record = row.copy()
            for position in (
                Position
                # [pos for pos in Position if not cls._RULES[pos]]
                if record[RuleFields.POSITIONS] == RuleValue.ANY
                else record[RuleFields.POSITIONS]
            ):
                # Replace a generic rule (= valid for any position) with a specific one.
                rulelist: list[RuleDefinition] = ruledict[position][record[RuleFields.RULETYPE]]
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
                        conditions={
                            record[parm]: record[val]
                            for parm, val in [
                                (RuleFields.CONDITION1, RuleFields.CONDITIONVALUE1),
                                (RuleFields.CONDITION2, RuleFields.CONDITIONVALUE2),
                            ]
                            if record[parm]
                        },
                        action={record[RuleFields.ACTION]: record[RuleFields.ACTIONVALUE]},
                    )
                )
        return ruledict

    @classmethod
    def get_kempyung_pitch(cls, position, pitch: Pitch, inverse: bool = False) -> Pitch | None:
        return next(
            (
                (p if inverse else k)
                for p, k in cls.RULES[position][RuleType.KEMPYUNG][0].action[RuleAction.DEFINITION]
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
        oct_interval = Instrument.interval(Tone(pitch=Pitch.DONG, octave=0), Tone(pitch=Pitch.DONG, octave=1))
        inv = -1 if inverse else 1
        k_list = [
            Tone(pitch=kempyung_pitch, octave=octave)
            for octave in try_octaves
            if Tone(pitch=kempyung_pitch, octave=octave) in Instrument.get_range(position, extended_range)
            and (
                not exact_octave_match
                or 0 < inv * Instrument.interval(tone, Tone(pitch=kempyung_pitch, octave=octave)) < oct_interval
            )
        ]
        # Put kempyung tones that are higher than the reference tone first.
        return sorted(
            k_list, key=lambda x: [0, 1, 2, -1, -2].index(math.floor(Instrument.interval(tone, x) / oct_interval))
        )

    @classmethod
    def get_casting_rule(
        cls, position: Position, note: GenericNote, unisono_positions: set[Position]
    ) -> RuleDefinition:
        rules: list[RuleDefinition] = cls.RULES.get(position, {}).get(RuleType.CAST_TO_POSITION, None)
        if rules:
            # Try to match a rule, starting with the most specific match
            rule = (
                next(
                    (
                        rule
                        for rule in rules
                        if set(rule.conditions[RuleCondition.SHARED_BY]) == set(unisono_positions)
                        and note.effect in set(rule.conditions[RuleCondition.PATTERNTYPE])
                    ),
                    None,
                )
                or next(
                    (
                        rule
                        for rule in rules
                        if set(rule.conditions[RuleCondition.SHARED_BY]) == set(unisono_positions)
                        and rule.conditions[RuleCondition.PATTERNTYPE] is RuleValue.ANY
                    ),
                    None,
                )
                or next(
                    (
                        rule
                        for rule in rules
                        if rule.conditions[RuleCondition.SHARED_BY] is RuleValue.ANY
                        and note.effect in set(rule.conditions[RuleCondition.PATTERNTYPE])
                    ),
                    None,
                )
                or next(
                    (
                        rule
                        for rule in rules
                        if rule.conditions[RuleCondition.SHARED_BY] is RuleValue.ANY
                        and rule.conditions[RuleCondition.PATTERNTYPE] is RuleValue.ANY
                    ),
                    None,
                )
            )
            if rule:
                return rule.action[RuleAction.TRANSFORM]
        return None

    @classmethod
    def cast_to_position(
        cls,
        note: GenericNote,
        position: Position,
        all_positions: set[Position],
        metadata: defaultdict[MetaType, list[MetaData]],
        inverse: bool = False,
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

        # Rules only apply to melodic pitches.
        if not note.is_melodic():
            return note.to_tone()

        rule = (
            [RuleValue.SAME_TONE_EXTENDED]
            if len(all_positions) == 1
            else cls.get_casting_rule(position, note, set(all_positions))
        )
        if not rule:
            raise ValueError(f"No unisono rule found for {position}.")

        # Check metadata that affects the rule and modify the rule accordingly
        for meta in metadata[MetaType.AUTOKEMPYUNG]:
            if meta.status == MetaDataSwitch.OFF and (not meta.positions or position in meta.positions):
                if RuleValue.EXACT_KEMPYUNG in rule:
                    rule = rule.copy()
                    rule.remove(RuleValue.EXACT_KEMPYUNG)

        tone = note.to_tone()
        for action in rule:
            match action:
                case RuleValue.SAME_TONE:
                    # retain pitch and octave
                    tones = Instrument.get_tones_within_range(tone, position, extended_range=False, match_octave=True)
                case RuleValue.SAME_TONE_EXTENDED:
                    # retain pitch and octave
                    tones = Instrument.get_tones_within_range(tone, position, extended_range=True, match_octave=True)
                case RuleValue.SAME_PITCH:
                    # retain pitch, select octave within instrument's range
                    tones = Instrument.get_tones_within_range(tone, position, extended_range=False, match_octave=False)
                case RuleValue.SAME_PITCH_EXTENDED_RANGE:
                    # retain pitch, select octave within instrument's extended range
                    tones = Instrument.get_tones_within_range(tone, position, extended_range=True, match_octave=False)
                case RuleValue.EXACT_KEMPYUNG:
                    # select kempyung tone that lies immediately above the given tone
                    tones = cls.get_kempyung_tones_within_range(
                        tone, position, extended_range=False, exact_octave_match=True, inverse=inverse
                    )
                case RuleValue.KEMPYUNG:
                    # select kempyung pitch that lies within instrument's range
                    tones = cls.get_kempyung_tones_within_range(
                        tone, position, extended_range=False, exact_octave_match=False, inverse=inverse
                    )
                case _:
                    raise ValueError("Unknown action %s" % action)
            if tones:
                return Tone(pitch=tones[0].pitch, octave=tones[0].octave, transformation=action)
        raise ValueError("Could not assign %s to position %s" % (tone, position))

    def to_bound_notes(
        self, notes: list[GenericNote], position: Position, all_positions: list[Position], metadata: list[MetaData]
    ):
        bound_notes: list[Note | Pattern] = []
        for genericnote in notes:
            tone = self.cast_to_position(
                note=genericnote,
                position=position,
                all_positions=all_positions,
                metadata=metadata,
            )
            bound_note = NoteFactory.create_note(
                position=position,
                pitch=tone.pitch if tone else Pitch.NONE,
                octave=tone.octave if tone else None,
                effect=genericnote.effect,
                note_value=genericnote.note_value,
                transformation=tone.transformation,
            )
            if isinstance(genericnote.effect, PatternType):
                bound_note = Pattern(
                    position=position,
                    symbol=bound_note.symbol,
                    pitch=bound_note.pitch,
                    octave=bound_note.octave,
                    effect=bound_note.effect,
                    note_value=bound_note.note_value,
                    transformation=tone.transformation,
                )
            bound_notes.append(bound_note)
        return bound_notes
