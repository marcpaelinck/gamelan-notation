"""This module can be used to run applications.
The settings in the /settings/run-settings.yaml file determine which application will be executed.
"""

from src.common.constants import NotationFont
from src.notation2midi.dict_to_score import DictToScoreConverter
from src.notation2midi.notation5_to_dict import Notation5Parser
from src.notation2midi.score_to_midi import MidiGenerator
from src.notation2midi.score_to_notation import score_to_notation_file
from src.notation2midi.score_validation import ScoreValidator
from src.settings.classes import RunSettings
from src.settings.constants import Yaml
from src.settings.settings import get_run_settings, load_run_settings
from src.settings.settings_validation import validate_input_data
from src.soundfont.soundfont_generator import create_soundfont_files


def load_and_validate_run_settings(notation: dict[str, str] = None) -> RunSettings:
    run_settings = load_run_settings(notation)
    if run_settings.options.validate_settings:
        validate_input_data(run_settings)
    return run_settings


def notation_to_midi(run_settings: RunSettings):
    if run_settings.options.notation_to_midi:
        if run_settings.font.fontversion is NotationFont.BALIMUSIC5:
            font_parser = Notation5Parser(run_settings)
        else:
            raise Exception(f"Cannot parse font {run_settings.font.fontversion}.")
        notation = font_parser.parse_notation()
        score = DictToScoreConverter(notation).create_score()
        score = ScoreValidator(score).validate_score()
        MidiGenerator(score).create_midifile()

    if run_settings.options.notation_to_midi.save_corrected_to_file:
        score_to_notation_file(score)


def multiple_notations_to_midi(notations: list[str, str]):
    """Creates multiple notations

    Args:
        notations (list[tuple[str, str]]): list of (composition, part) pairs
    """
    for notation in notations:
        run_settings = load_and_validate_run_settings(notation)
        notation_to_midi(run_settings)


def single_run():
    run_settings = load_and_validate_run_settings()
    notation_to_midi(run_settings)


notations = [
    {Yaml.COMPOSITION: "sinomladrang-sp", Yaml.PART: "full"},
    {Yaml.COMPOSITION: "sinomladrang-sp", Yaml.PART: "pengawak"},
    {Yaml.COMPOSITION: "sinomladrang-sp", Yaml.PART: "pengecet"},
    {Yaml.COMPOSITION: "sinomladrang-gk", Yaml.PART: "full"},
    {Yaml.COMPOSITION: "lengker", Yaml.PART: "full"},
    {Yaml.COMPOSITION: "lengker", Yaml.PART: "penyalit"},
    {Yaml.COMPOSITION: "lengker", Yaml.PART: "pengecet"},
    {Yaml.COMPOSITION: "lengker", Yaml.PART: "pengawak"},
    {Yaml.COMPOSITION: "godekmiring", Yaml.PART: "full"},
    {Yaml.COMPOSITION: "godekmiring", Yaml.PART: "penyalit"},
    {Yaml.COMPOSITION: "godekmiring", Yaml.PART: "pengecet"},
    {Yaml.COMPOSITION: "godekmiring", Yaml.PART: "penyalit-angsel"},
    {Yaml.COMPOSITION: "godekmiring", Yaml.PART: "pengawak"},
    {Yaml.COMPOSITION: "cendrawasih", Yaml.PART: "full"},
]
notations = [
    # {Yaml.COMPOSITION: "godekmiring", Yaml.PART: "full"},
    {Yaml.COMPOSITION: "sinomladrang-gk", Yaml.PART: "full"},
]
get_run_settings()
single_run()

# multiple_notations_to_midi(notations)
