"""This module enables the user to create a 'pipeline', which is a list of actions
that should be performed sequentially.
e.g. :  1. Read and process soundfiles
        2. Create frequency spectra
        3. Determine partials
        4. Create and plot a dissonance graph
Most Actions produce output that can be used by subsequent actions in the pipeline.
Before running a sequence, the PipeLine class checks its validity by determining whether
the input that is required in each step is available from previous steps. The required
input for each step can consist of multiple values or objects.
The application mostly uses Pydantic object structures to pass the data from one
step to the other. The output of intermediate steps can be saved to JSON files and retrieved
later. This enables to read and use this data at the start of a pipeline instead of
re-running the steps that were used to generate this data.
"""

from typing import Any, Type

from src.common.logger import Logging
from src.notation2midi.classes import Agent
from src.notation2midi.pipeline.export_to_midiplayer import (
    MidiPlayerUpdatePartAgent,
    MidiPlayerUpdatePdfAgent,
)
from src.notation2midi.pipeline.notation_to_score import ScoreCreatorAgent
from src.notation2midi.pipeline.parse_notation import NotationParserAgent
from src.notation2midi.pipeline.score_to_midi import MidiGeneratorAgent
from src.notation2midi.pipeline.score_to_pdf import PDFGeneratorAgent
from src.notation2midi.pipeline.score_validation import ScoreValidationAgent
from src.settings.classes import RunSettings
from src.settings.settings import Settings
from src.settings.settings_validation import SettingsValidationAgent

logger = Logging.get_logger(__name__)


class PipeLine:
    """
    The pipeline enables to execute a sequence of functions that generate output for subsequent
    functions. The sequence is determined in the `pipe` parameter.
    Currently, only data of types InstrumentGroupName, InstrumentGroup or AggregatedPartialDict
    Can be passed from one function to the other.
    Additional pre-set parameters can be set through the Step objects in the Step class definition.
    These parameters can later be overuled by calling the `param` method of a Step object.

    Returns:
        PipeLine: A PipeLine object.
    """

    pipe: list[Type[Agent]] = None  # list of actions that should be performed sequentially
    data: dict[Agent.InputOutputType, Any] = {}  # dict to which results of piped actions will be added

    def __init__(self, run_settings: RunSettings, pipe: list[Type[Agent]]):
        """
        Args:
            groupname (InstrumentGroupName): The instrument group. The first step action will receive this value
                                             as input and should not expect any other input.
            pipe (Pipe): A list of Step values which defines the sequence in which actions should be performed.
            Warning: Illegal sequence if the sequence of the Pipe object is infeasible. This is the case
                     if an action expects input that is not created by any preceding step.
        """
        self.run_settings = run_settings
        self.data[Agent.InputOutputType.RUNSETTINGS] = run_settings
        self.pipe = pipe

        if not self.is_valid_pipe():
            logger.error("Aborting script.")
            exit()

    def is_valid_pipe(self) -> bool:
        available_data = {Agent.InputOutputType.RUNSETTINGS: RunSettings}
        agentclass: Type[Agent]
        # Follow the pipeline flow, and check that the required input of each step has been created previously.
        for agentclass in self.pipe:
            if agentclass.EXPECTED_INPUT_TYPES:
                missing_input = ", ".join(
                    [
                        f"'{keyword.value}'"
                        for keyword in agentclass.EXPECTED_INPUT_TYPES
                        if keyword not in available_data
                    ]
                )
                if missing_input:
                    logger.error(
                        f"Invalid pipeline sequence: missing input {missing_input} for {agentclass.LOGGING_MESSAGE.name}."
                    )
                    return False
            if agentclass.RETURN_TYPE:
                if isinstance(agentclass.RETURN_TYPE, Agent.InputOutputType):
                    available_data |= {agentclass.RETURN_TYPE: True}
                else:
                    for outtype in agentclass.RETURN_TYPE:
                        available_data |= {outtype: True}
        return True

    def __get_data_items__(self, datatypes: dict[str, type]):
        return {keyword: self.data[datatype] for keyword, datatype in datatypes.items()}

    def do_quit(self):
        logger.error("Program halted")
        exit()

    def execute(self):
        logger.info("Starting pipeline")
        for agentclass in self.pipe:
            # Check that the agent is required to run
            if not agentclass.run_condition_satisfied(self.run_settings):
                continue
            # Check that all required input values are available
            if agentclass.EXPECTED_INPUT_TYPES:
                missing_values = [
                    f"'{keyword}'"
                    for keyword in agentclass.EXPECTED_INPUT_TYPES
                    if self.data.get(keyword, None) is None
                ]
                if missing_values:
                    logger.error(
                        "Missing input value(s) %s for %s", ", ".join(missing_values), agentclass.LOGGING_MESSAGE
                    )
                    self.do_quit()
            # Retrieve the required parameters
            param_dict = (
                {
                    keyword.value: value
                    for keyword, value in self.data.items()
                    if keyword in agentclass.EXPECTED_INPUT_TYPES
                }
                if agentclass.EXPECTED_INPUT_TYPES
                else {}
            )
            agent = agentclass(**param_dict)
            result = agent.run()
            if agent.has_errors:
                self.do_quit()
            if result:
                if (
                    isinstance(result, tuple)
                    and isinstance(agent.RETURN_TYPE, tuple)
                    and len(result) == len(agent.RETURN_TYPE)
                ):
                    for return_type, return_value in zip(agent.RETURN_TYPE, result):
                        self.data[return_type] = return_value
                else:
                    self.data[agentclass.RETURN_TYPE] = result


# FULL SEQUENCE STARTS HERE
PIPE = [
    SettingsValidationAgent,
    NotationParserAgent,
    ScoreCreatorAgent,
    ScoreValidationAgent,
    MidiGeneratorAgent,
    PDFGeneratorAgent,
    MidiPlayerUpdatePartAgent,
    MidiPlayerUpdatePdfAgent,
]

if __name__ == "__main__":
    logger.open_logging("NOTATION2MIDI")
    pipeline = PipeLine(run_settings=Settings.get(), pipe=PIPE)
    pipeline.execute()
