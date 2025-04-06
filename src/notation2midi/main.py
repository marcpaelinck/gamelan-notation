"""This module can be used to perform a complete run cycle (notation -> midi output)."""

from tkinter.messagebox import askyesno

from src.common.constants import NotationFontVersion
from src.common.logger import Logging
from src.notation2midi.dict_to_score import DictToScoreConverter
from src.notation2midi.export_to_midiplayer import MidiPlayerExportAgent
from src.notation2midi.notation_parser_tatsu import NotationTatsuParser
from src.notation2midi.score2notation.score_to_notation import score_to_notation_file
from src.notation2midi.score2notation.score_to_pdf import ScoreToPDFConverter
from src.notation2midi.score_to_midi import MidiGenerator
from src.notation2midi.score_validation import ScoreValidator
from src.settings.classes import RunSettings, RunType
from src.settings.settings import Settings
from src.settings.settings_validation import SettingsValidator

logger = Logging.get_logger(__name__)


def load_and_validate_run_settings(notation_id: str = None, part_id: str = None) -> RunSettings:
    run_settings = Settings.get(notation_id=notation_id, part_id=part_id)
    SettingsValidator(run_settings).validate_input_data()
    return run_settings


def notation_to_midi(run_settings: RunSettings):
    """Runs the parsers in a pipeline"""
    success = False
    if run_settings.options.notation_to_midi:

        if run_settings.fontversion is NotationFontVersion.BALIMUSIC5:
            font_parser = NotationTatsuParser(run_settings)
        else:
            raise ValueError(f"Cannot parse font {run_settings.fontversion}.")
        notation = font_parser.parse_notation()
        if notation:
            dict2score = DictToScoreConverter(notation)
            score = dict2score.create_score()
        if score:
            scorevalidator = ScoreValidator(score)
            score = scorevalidator.validate_score()
        if score:
            midigenerator = MidiGenerator(score)
            part = midigenerator.create_midifile()
            midiplayerexporter = MidiPlayerExportAgent(part)
            success = midiplayerexporter.update_midiplayer_content()

    if success and run_settings.options.notation_to_midi.save_corrected_to_file:
        score_to_notation_file(score)
    if (
        success
        and run_settings.options.notation_to_midi.save_pdf_notation
        and run_settings.part_id in run_settings.notation.generate_pdf_part_ids
    ):
        scoretopdfconverter = ScoreToPDFConverter(score)
        pdf_filename = scoretopdfconverter.create_notation()
        midiplayerexporter = MidiPlayerExportAgent(pdf_file=pdf_filename)
        midiplayerexporter.update_midiplayer_content()


def multiple_notations_to_midi(run_settings: RunSettings):
    """Creates multiple notations

    Args:
        notations (list[tuple[str, str]]): list of (composition, part) pairs
    """
    notation_list = list(run_settings.configdata.notations.items())
    runtype = run_settings.options.notation_to_midi.runtype
    is_production_run = run_settings.options.notation_to_midi.is_production_run
    for notation_key, notation_info in notation_list:
        if runtype in notation_info.include_in_run_types and (
            not is_production_run or notation_info.include_in_production_run
        ):
            for part_key, _ in notation_info.parts.items():
                run_settings = Settings.get(notation_id=notation_key, part_id=part_key)
                notation_to_midi(run_settings)


def single_run(run_settings: RunSettings):
    # run_settings = load_and_validate_run_settings()
    notation_to_midi(run_settings)


def main():
    logger.open_logging("NOTATION2MIDI")
    run_settings = Settings.get()
    logger.open_logging(f"{run_settings.notation.title} - {run_settings.notation.part.name}")
    SettingsValidator(run_settings).validate_input_data()
    run_settings = load_and_validate_run_settings()
    if not run_settings.options.notation_to_midi.is_production_run or askyesno(
        "Warning", "Running production version. Continue?"
    ):
        if run_settings.options.notation_to_midi.runtype is RunType.RUN_ALL:
            multiple_notations_to_midi(run_settings)
        else:
            single_run(run_settings)
    logger.close_logging()


if __name__ == "__main__":
    main()
