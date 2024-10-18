"""This module can be used to run applications.
The settings in the /settings/run-settings.yaml file determine which application will be executed.
"""

from src.common.classes import RunSettings
from src.notation2midi.notation_to_midi import convert_notation_to_midi
from src.settings.settings import get_run_settings
from src.settings.settings_validation import validate_input_data
from src.soundfont.soundfont_generator import create_soundfont_file


def import_run_settings() -> RunSettings:
    run_settings = get_run_settings()
    if run_settings.options.validate_settings:
        validate_input_data(run_settings)
    return run_settings


run_settings = import_run_settings()

if run_settings.options.notation_to_midi.run:
    convert_notation_to_midi(run_settings)

if run_settings.options.soundfont.run:
    create_soundfont_file(run_settings)
