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
    logger.open_logging(f"{run_settings.notationfile.title} - {run_settings.notationfile.part.name}")
    pipeline = PipeLine(run_settings=run_settings, pipe=PIPE)
    pipeline.execute()


def run_multiple_pipelines(run_settings: RunSettings):
    """Creates multiple notations

    Args:
        run_settings (RunSettings): list of (composition, part) pairs
    """
    runtype = run_settings.options.notation_to_midi.runtype
    is_production_run = run_settings.options.notation_to_midi.is_production_run

    # Create a list of the notation entries that should be processed, based on
    # their include_in_run_types and include_in_production_run attributes.
    notation_list = [
        (notation_key, notation_info)
        for notation_key, notation_info in run_settings.configdata.notationfiles.items()
        if runtype in notation_info.include_in_run_types
        and (not is_production_run or notation_info.include_in_production_run)
    ]
    # Run the pipeline for each part of each song.
    for notation_key, notation_info in notation_list:
        for part_key, _ in notation_info.parts.items():
            run_settings = Settings.get(notation_id=notation_key, part_id=part_key)
            run_pipeline(run_settings)


def main():
    logger.open_logging("NOTATION2MIDI")
    run_settings = Settings.get()
    if not run_settings.options.notation_to_midi.is_production_run or askyesno(
        "Warning", "Running production version. Continue?"
    ):
        if run_settings.options.notation_to_midi.runtype is RunType.RUN_ALL:
            run_multiple_pipelines(run_settings)
        else:
            run_pipeline(run_settings)
    logger.close_logging()


if __name__ == "__main__":
    main()
