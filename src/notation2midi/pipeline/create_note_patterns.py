from typing import override

from src.common.classes import Gongan, Score
from src.notation2midi.classes import Agent
from src.notation2midi.note_patterns import NotePattern, NotePatternGenerator
from src.settings.classes import RunSettings


class NotePatternGeneratorAgent(Agent):
    """Parser that converts notation documents into a hierarchical dict structure. It uses the
    Tatsu library in combination with ebnf grammar files.
    The parser has no 'knowledge' about the instruments and idiom of the music. It only checks the
    basic structure of the notation as described in the grammar files and reports any syntax error.
    """

    AGENT_TYPE = Agent.AgentType.NOTEPATTERNCREATOR
    EXPECTED_INPUT_TYPES = (Agent.InputOutputType.SCORE,)
    RETURN_TYPE = None

    score: Score

    def __init__(self, score: Score):
        super().__init__(score.settings)
        self.score = score
        self.pattern_generator = NotePatternGenerator(self.run_settings)
        self.patterns: list[NotePattern] = []

    @override
    @classmethod
    def run_condition_satisfied(cls, run_settings: RunSettings):
        return True

    def _generate_patterns(self, gongan: Gongan) -> None:
        for beat in self.beat_iterator(gongan):
            for position, measure in beat.measures.items():
                for passnr, pass_ in measure.passes.items():
                    self.curr_line_nr = pass_.line
                    for note in pass_.notes:
                        note.pattern.append(note.model_copy())
                    try:
                        # self.patterns += self.pattern_generator.update_grace_notes_octaves(
                        #     beat=beat, position=position, passnr=passnr
                        # )
                        self.patterns += self.pattern_generator.generate_tremolo(
                            beat=beat,
                            position=position,
                            passnr=passnr,
                            errorlogger=self.logerror,
                        )
                    except ValueError as e:
                        self.logerror(str(e))

    @override
    def _main(self):
        for gongan in self.gongan_iterator(self.score):
            self._generate_patterns(gongan)
        for pattern in self.patterns:
            pattern.note.pattern.clear()
            pattern.note.pattern.extend(pattern.pattern)
        return None
