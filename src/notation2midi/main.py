"""This module can be used to perform a complete run cycle (notation -> midi output).
"""

from src.common.constants import NotationFont, Position
from src.notation2midi.dict_to_score import DictToScoreConverter
from src.notation2midi.notation_parser_tatsu import NotationTatsuParser
from src.notation2midi.score_to_midi import MidiGenerator
from src.notation2midi.score_to_notation import score_to_notation_file
from src.notation2midi.score_to_pdf import ScoreToPDFConverter
from src.notation2midi.score_validation import ScoreValidator
from src.settings.classes import RunSettings, RunType
from src.settings.constants import Yaml
from src.settings.settings import get_run_settings, load_run_settings
from src.settings.settings_validation import SettingsValidator


def load_and_validate_run_settings(notation: dict[str, str] = None) -> RunSettings:
    run_settings = load_run_settings(notation)
    if run_settings.options.validate_settings:
        SettingsValidator(run_settings).validate_input_data()
    return run_settings


def notation_to_midi(run_settings: RunSettings):
    if run_settings.options.notation_to_midi:
        if run_settings.font.fontversion is NotationFont.BALIMUSIC5:
            font_parser = NotationTatsuParser(run_settings)
        else:
            raise Exception(f"Cannot parse font {run_settings.font.fontversion}.")
        notation = font_parser.parse_notation()
        if notation:
            score = DictToScoreConverter(notation).create_score()
        if score:
            score = ScoreValidator(score).validate_score()
        if score:
            success = MidiGenerator(score).create_midifile()

    if success and run_settings.options.notation_to_midi.save_corrected_to_file:
        score_to_notation_file(score)
    if success and run_settings.options.notation_to_midi.save_pdf_notation:
        ScoreToPDFConverter(score).create_notation()


def multiple_notations_to_midi(run_settings: RunSettings):
    """Creates multiple notations

    Args:
        notations (list[tuple[str, str]]): list of (composition, part) pairs
    """
    for notation_key, notation_info in run_settings.notations.items():
        if run_settings.options.notation_to_midi.runtype in notation_info.include_in_run_types:
            for part_key, part_info in notation_info.parts.items():
                run_settings = load_and_validate_run_settings({Yaml.COMPOSITION: notation_key, Yaml.PART_ID: part_key})
                notation_to_midi(run_settings)


def single_run():
    run_settings = load_and_validate_run_settings()
    notation_to_midi(run_settings)


if __name__ == "__main__":
    run_settings = get_run_settings()
    if run_settings.options.notation_to_midi.runtype is RunType.RUN_ALL:
        multiple_notations_to_midi(run_settings)
    else:
        single_run()
