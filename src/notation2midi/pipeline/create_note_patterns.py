from typing import ClassVar, override

from src.common.classes import Score
from src.common.notes import Note
from src.notation2midi.classes import Agent
from src.notation2midi.patterns.pattern import PatternGenerator
from src.notation2midi.patterns.tremolo_pattern import TremoloPatternGenerator
from src.settings.classes import RunSettings


class NotePatternGeneratorAgent(Agent):
    """Parser that converts notation documents into a hierarchical dict structure. It uses the
    Tatsu library in combination with ebnf grammar files.
    The parser has no 'knowledge' about the instruments and idiom of the music. It only checks the
    basic structure of the notation as described in the grammar files and reports any syntax error.
    """

    LOGGING_MESSAGE = "GENERATING NOTE PATTERNS"
    EXPECTED_INPUT_TYPES = (Agent.InputOutputType.BOUNDSCORE,)
    RETURN_TYPE = Agent.InputOutputType.PATTERNSCORE

    _PATTERNCLASSES: ClassVar[list[PatternGenerator]] = [TremoloPatternGenerator]

    score: Score

    def __init__(self, bound_score: Score):
        super().__init__(bound_score.settings)
        self.score = bound_score
        self.pattern_generators: list[PatternGenerator] = [
            ruleclass(self.run_settings) for ruleclass in self._PATTERNCLASSES
        ]

    @override
    @classmethod
    def run_condition_satisfied(cls, run_settings: RunSettings):
        return True

    def execute(self, notes: list[Note]):
        for generator in self.pattern_generators:
            generator.create_pattern(notes=notes)

    @override
    def _main(self):
        for gongan in self.gongan_iterator(self.score):
            for beat in self.beat_iterator(gongan):
                for measure in beat.measures.values():
                    for pass_ in measure.passes.values():
                        self.curr_line_nr = pass_.line
                        self.execute(pass_.notes)
