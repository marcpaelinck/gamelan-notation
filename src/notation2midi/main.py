"""This module can be used to perform a complete run cycle (notation -> midi output)."""

from tkinter.messagebox import askyesno

from src.common.constants import NotationFontVersion
from src.common.logger import get_logger
from src.notation2midi.dict_to_score import DictToScoreConverter
from src.notation2midi.notation_parser_tatsu import NotationTatsuParser
from src.notation2midi.score2notation.score_to_notation import score_to_notation_file
from src.notation2midi.score2notation.score_to_pdf import ScoreToPDFConverter
from src.notation2midi.score_to_midi import MidiGenerator
from src.notation2midi.score_validation import ScoreValidator
from src.settings.classes import RunSettings, RunType
from src.settings.settings import get_run_settings, load_run_settings
from src.settings.settings_validation import SettingsValidator

logger = get_logger(__name__)


def load_and_validate_run_settings(notation_id: str = None, part_id: str = None) -> RunSettings:
    run_settings = load_run_settings(notation_id=notation_id, part_id=part_id)
    if run_settings.options.validate_settings:
        SettingsValidator(run_settings).validate_input_data()
    return run_settings


def notation_to_midi(run_settings: RunSettings):
    success = False
    if run_settings.options.notation_to_midi:
        if run_settings.fontversion is NotationFontVersion.BALIMUSIC5:
            font_parser = NotationTatsuParser(run_settings)
        else:
            raise ValueError(f"Cannot parse font {run_settings.fontversion}.")
        notation = font_parser.parse_notation()
        if notation:
            score = DictToScoreConverter(notation).create_score()
        if score:
            score = ScoreValidator(score).validate_score()
        if score:
            success = MidiGenerator(score).create_midifile()

    if success and run_settings.options.notation_to_midi.save_corrected_to_file:
        score_to_notation_file(score)
    if (
        success
        and run_settings.options.notation_to_midi.save_pdf_notation
        and run_settings.part_id in run_settings.notation.generate_pdf_part_ids
    ):
        ScoreToPDFConverter(score).create_notation()
    logger.info("")


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
                run_settings = load_and_validate_run_settings(notation_id=notation_key, part_id=part_key)
                notation_to_midi(run_settings)


def single_run():
    run_settings = load_and_validate_run_settings()
    notation_to_midi(run_settings)


def main():
    run_settings = get_run_settings()
    if not run_settings.options.notation_to_midi.is_production_run or askyesno(
        "Warning", "Running production version. Continue?"
    ):
        if run_settings.options.notation_to_midi.runtype is RunType.RUN_ALL:
            multiple_notations_to_midi(run_settings)
        else:
            single_run()


if __name__ == "__main__":
    main()
