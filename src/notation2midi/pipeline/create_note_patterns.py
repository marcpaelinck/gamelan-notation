from typing import override

from src.common.classes import Gongan, Score
from src.notation2midi.classes import Agent
from src.notation2midi.note_patterns import NotePatternGenerator
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

    score: Score

    def __init__(self, bound_score: Score):
        super().__init__(bound_score.settings)
        self.score = bound_score
        self.pattern_generator = NotePatternGenerator(self.run_settings)

    @override
    @classmethod
    def run_condition_satisfied(cls, run_settings: RunSettings):
        return True

    def _generate_patterns(self, gongan: Gongan) -> None:
        for beat in self.beat_iterator(gongan):
            for position, measure in beat.measures.items():
                for passnr, pass_ in measure.passes.items():
                    self.curr_line_nr = pass_.line
                    try:
                        self.pattern_generator.generate_tremolo(beat=beat, position=position, passnr=passnr)
                    except ValueError as e:
                        self.logerror(str(e))

    @override
    def _main(self):
        for gongan in self.gongan_iterator(self.score):
            self._generate_patterns(gongan)
        return self.score
