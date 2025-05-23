from typing import override

from src.common.classes import Score
from src.notation2midi.classes import Agent
from src.notation2midi.execution import Execution
from src.settings.classes import RunSettings


class ExecutionCreatorAgent(Agent):
    """Parser that converts notation documents into a hierarchical dict structure. It uses the
    Tatsu library in combination with ebnf grammar files.
    The parser has no 'knowledge' about the instruments and idiom of the music. It only checks the
    basic structure of the notation as described in the grammar files and reports any syntax error.
    """

    AGENT_TYPE = Agent.AgentType.EXECUTIONCREATOR
    EXPECTED_INPUT_TYPES = (Agent.InputOutputType.RUNSETTINGS,)
    RETURN_TYPE = Agent.InputOutputType.EXECUTION

    score: Score

    def __init__(self, score: Score):
        super().__init__(score.settings)
        self.score = score

    @override
    @classmethod
    def run_condition_satisfied(cls, run_settings: RunSettings):
        return True

    @override
    def _main(self) -> Execution:
        pass
