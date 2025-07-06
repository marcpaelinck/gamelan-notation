from typing import ClassVar, override

from src.common.classes import Measure, Score
from src.common.constants import Position
from src.notation2midi.classes import Agent
from src.notation2midi.metadata_classes import MetaData
from src.notation2midi.rules.rule import Rule
from src.notation2midi.rules.rule_cast_to_position import RuleCastToPosition

# from src.notation2midi.rules.rule_process_modifiers import RuleProcessModifiers
from src.notation2midi.rules.rule_set_gracenote_octave import RuleSetGracenoteOctave
from src.settings.classes import RunSettings


class RulesAgent(Agent):
    """Casts generic notes to specific instruments by applying instrument rules, and returns
       a Score object containing BoundNotes: notes that are bound to a specific instrument position.
        - Splits staves having multiple instrument position tags into staves for individual positions.
        - Updates the octave of grace notes.
    also updateS grace note octaves"""

    LOGGING_MESSAGE = "APPLYING RULES"
    EXPECTED_INPUT_TYPES = (Agent.InputOutputType.GENERICSCORE,)
    RETURN_TYPE = Agent.InputOutputType.BOUNDSCORE

    _RULECLASSES: ClassVar[list[Rule]] = [RuleCastToPosition, RuleSetGracenoteOctave]

    score: Score

    def __init__(self, generic_score: Score):
        super().__init__(generic_score.settings)
        self.score = generic_score
        self.rules: list[Rule] = [ruleclass(self.run_settings) for ruleclass in self._RULECLASSES]

    @override
    @classmethod
    def run_condition_satisfied(cls, run_settings: RunSettings):
        return True

    def execute(self, pass_: Measure.Pass, position: Position, all_positions: list[Position], metadata: list[MetaData]):
        for rule in self.rules:
            try:
                pass_.notes = rule.fire(pass_=pass_, position=position, all_positions=all_positions, metadata=metadata)
            except ValueError as e:
                self.logerror(str(e))
        return pass_.notes

    @override
    def _main(self):
        for rule in self.rules:
            self.loginfo(f"Rule: {rule.NAME}")
        for gongan in self.gongan_iterator(self.score):
            for beat in self.beat_iterator(gongan):
                for position, measure in beat.measures.items():
                    for pass_ in self.pass_iterator(measure):
                        bound_notes = self.execute(
                            pass_=pass_,
                            position=position,
                            all_positions=measure.all_positions,
                            metadata=gongan.metadata,
                        )
                        pass_.notes = bound_notes
        return self.score
