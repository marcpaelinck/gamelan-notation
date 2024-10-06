import pandas as pd

from src.notation2midi.settings import get_run_settings, read_settings


def create_soundfont_file():
    run_settings = get_run_settings()
    read_settings(run_settings)
