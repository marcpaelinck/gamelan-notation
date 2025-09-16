"""This module can be used to perform a complete run cycle (notation -> midi output)."""

from tkinter.messagebox import askyesno

from src.common.logger import Logging
from src.notation2midi.pipeline.apply_rules import RulesAgent
from src.notation2midi.pipeline.create_execution import ExecutionCreatorAgent
from src.notation2midi.pipeline.create_note_patterns import NotePatternGeneratorAgent
from src.notation2midi.pipeline.export_to_midiplayer import (
    MidiPlayerUpdatePartAgent,
    MidiPlayerUpdatePdfAgent,
)
from src.notation2midi.pipeline.notation_to_score import ScoreCreatorAgent
from src.notation2midi.pipeline.parse_notation import NotationParserAgent
from src.notation2midi.pipeline.pipeline import PipeLine
from src.notation2midi.pipeline.score_postprocessing import ScorePostprocessAgent
from src.notation2midi.pipeline.score_to_json import JsonGeneratorAgent
from src.notation2midi.pipeline.score_to_midi import MidiGeneratorAgent
from src.notation2midi.pipeline.score_to_notation import ScoreToNotationAgent
from src.notation2midi.pipeline.score_to_pdf import PDFGeneratorAgent
from src.notation2midi.pipeline.score_validation import ScoreValidationAgent
from src.notation2midi.pipeline.settings_validation import SettingsValidationAgent
from src.settings.classes import RunSettings, RunType
from src.settings.settings import Settings

logger = Logging.get_logger(__name__)

PIPE = [
    SettingsValidationAgent,
    NotationParserAgent,  # -> Parses the notation to a structure that reflects the notation
    ScoreCreatorAgent,  # -> Creates a Score object: structure that is used internally
    RulesAgent,  # -> Applies transformations such as creating multiple staves from a single 'unisono' stave
    NotePatternGeneratorAgent,  # -> Creates sequences of Note objects to emulate patterns such as tremolo or norot.
    ScorePostprocessAgent,  # Fills empty and shorthand beats + applies metadata. -> CompleteScore
    ScoreValidationAgent,  # Validates the score and performs corrections if required.
    ExecutionCreatorAgent,  # Creates a score Execution: the flow (gongan sequence), tempi and dynamics.
    MidiGeneratorAgent,  # Generates MIDI output.
    JsonGeneratorAgent,  # Generates JSON output.
    PDFGeneratorAgent,  # Generates a human-readable PDF score.
    ScoreToNotationAgent,  # Generates a corrected and standardized input file.
    MidiPlayerUpdatePartAgent,  # Updates the JSON settings file of the Front End application.
    MidiPlayerUpdatePdfAgent,
]


def run_pipeline(run_settings: RunSettings):
    """Creates a single notation which is determined by the settings `notation_id` and `part_id`
    in notation2midi.yaml.
    Args:
        run_settings (RunSettings): Settings and configuration.
    """
    logger.open_logging(f"{run_settings.notation_settings.title} - {run_settings.part_id}")
    pipeline = PipeLine(run_settings=run_settings, pipe=PIPE)
    pipeline.execute()


def run_multiple_pipelines(run_settings: RunSettings):
    """Creates multiple notations

    Args:
        run_settings (RunSettings): list of (composition, part) pairs
    """
    run_type = run_settings.options.notation_to_midi.run_type

    # Create a list of the notation entries that should be processed, based on
    # their run_types.
    notation_list = [
        (notation_id, part_id)
        for (notation_id, part_id), notation_info in run_settings.notation_settings_dict.items()
        if run_type in notation_info.run_types
        and (notation_id == run_settings.notation_id or not run_settings.notation_id)
    ]
    # Run the pipeline for each part of each song.
    for notation_id, part_id in notation_list:
        run_settings = Settings.get(notation_id=notation_id, part_id=part_id)
        run_pipeline(run_settings)


def main():
    logger.open_logging("NOTATION2MIDI")
    run_settings = Settings.get()
    if not run_settings.options.notation_to_midi.run_type is RunType.PRODUCTION or askyesno(
        "Warning", "Running production version. Continue?"
    ):
        if run_settings.notation_id and run_settings.part_id:
            run_pipeline(run_settings)
        elif run_settings.options.notation_to_midi.run_type is RunType.INTEGRATION_TEST or askyesno(
            "Warning",
            f"Processing all notation files{" for " + run_settings.notation_id if run_settings.notation_id else ""}. Continue?",
        ):
            run_multiple_pipelines(run_settings)
    logger.close_logging()


if __name__ == "__main__":
    main()
