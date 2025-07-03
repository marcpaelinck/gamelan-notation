"""This module can be used to perform a complete run cycle (notation -> midi output)."""

from tkinter.messagebox import askyesno

from src.common.logger import Logging
from src.common.pipeline import PipeLine
from src.notation2midi.pipeline.apply_rules import RulesAgent
from src.notation2midi.pipeline.create_execution import ExecutionCreatorAgent
from src.notation2midi.pipeline.create_note_patterns import NotePatternGeneratorAgent
from src.notation2midi.pipeline.export_to_midiplayer import (
    MidiPlayerUpdatePartAgent,
    MidiPlayerUpdatePdfAgent,
)
from src.notation2midi.pipeline.notation_to_score import ScoreCreatorAgent
from src.notation2midi.pipeline.parse_notation import NotationParserAgent
from src.notation2midi.pipeline.score_postprocessing import ScorePostprocessAgent
from src.notation2midi.pipeline.score_to_midi import MidiGeneratorAgent
from src.notation2midi.pipeline.score_to_notation import ScoreToNotationAgent
from src.notation2midi.pipeline.score_to_pdf import PDFGeneratorAgent
from src.notation2midi.pipeline.score_validation import ScoreValidationAgent
from src.settings.classes import RunSettings, RunType
from src.settings.settings import Settings
from src.settings.settings_validation import SettingsValidationAgent

logger = Logging.get_logger(__name__)

PIPE = [
    SettingsValidationAgent,
    NotationParserAgent,  # -> NotationRecords
    ScoreCreatorAgent,  # -> Score with grouped instruments and UnboundNotes: pitch, modifiers
    RulesAgent,  # Processes notation for instrument groups: casts notes to individual instruments. -> IScore with BoundNotes: octave, stroke and rel. duration + rule and transformation
    # should also update grace note octaves
    NotePatternGeneratorAgent,  # -> PattScore: Score with enhanced BoundNotes containing pattern(MidiNotes) + UUID
    ScorePostprocessAgent,  # Fills empty and shorthand beats + applies metadata. -> CompleteScore
    ScoreValidationAgent,
    ExecutionCreatorAgent,  # Creates Execution for the ExtScore -> Execution
    MidiGeneratorAgent,
    PDFGeneratorAgent,
    ScoreToNotationAgent,
    MidiPlayerUpdatePartAgent,
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
