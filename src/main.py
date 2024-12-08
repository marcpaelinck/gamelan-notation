"""This module can be used to run applications.
The settings in the /settings/run-settings.yaml file determine which application will be executed.
"""

from src.common.classes import RunSettings
from src.notation2midi.font5_specific_code import Font5Parser
from src.notation2midi.notation_to_midi import Score2MidiConverter
from src.settings.settings import get_run_settings
from src.settings.settings_validation import validate_input_data
from src.soundfont.soundfont_generator import create_soundfont_files


def import_run_settings(notation: dict[str, str] = None) -> RunSettings:
    run_settings = get_run_settings(notation)
    if run_settings.options.validate_settings:
        validate_input_data(run_settings)
    return run_settings


def do_run(run_settings: RunSettings):
    if run_settings.options.notation_to_midi:
        fontparser = Font5Parser(run_settings)
        score = fontparser.parse_notation()
        score2midiconverter = Score2MidiConverter(score)
        score2midiconverter.convert_notation_to_midi()

    if run_settings.options.soundfont.run:
        create_soundfont_files(run_settings)


def multiple_notations_to_midi(notations: list[str, str]):
    """Creates multiple notations

    Args:
        notations (list[tuple[str, str]]): list of (composition, part) pairs
    """
    for notation in notations:
        run_settings = import_run_settings(notation)
        do_run(run_settings)


def single_run():
    run_settings = import_run_settings()
    do_run(run_settings)


notations = [
    {"composition": "sinomladrang-sp", "part": "full"},
    {"composition": "sinomladrang-sp", "part": "pengawak"},
    {"composition": "sinomladrang-sp", "part": "pengecet"},
    {"composition": "sinomladrang-gk", "part": "full"},
    {"composition": "lengker", "part": "full"},
    {"composition": "lengker", "part": "penyalit"},
    {"composition": "lengker", "part": "pengecet"},
    {"composition": "lengker", "part": "pengawak"},
    {"composition": "godekmiring", "part": "full"},
    {"composition": "godekmiring", "part": "penyalit"},
    {"composition": "godekmiring", "part": "pengecet"},
    {"composition": "godekmiring", "part": "penyalit-angsel"},
    {"composition": "godekmiring", "part": "pengawak"},
    {"composition": "cendrawasih", "part": "full"},
]
notations = [
    # {"composition": "godekmiring", "part": "full"},
    {"composition": "godekmiring", "part": "pengecet"},
]
single_run()
# multiple_notations_to_midi(notations)
