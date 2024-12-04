""" Creates an Excel soundfont definition file. This file can imported in the Viena application 
    to create a  Soundfont file (.sf2 format). See http://www.synthfont.com/The_Definitions_File.pdf

    Main method: create_soundfont_file()
"""

import os
import subprocess
import time

import pyautogui

from src.common.classes import RunSettings
from src.common.logger import get_logger
from src.common.lookups import LOOKUP
from src.settings.settings import get_run_settings
from src.soundfont.soundfont_textfile import SoundfontTextfile

logger = get_logger(__name__)


def create_soundfont_definition_file(run_settings: RunSettings) -> None:
    """Creates a text file with soundfont definitions that can be imported into the Viena application.

    Args:
        run_settings (RunSettings): _description_
    """
    logger.info("======== SOUNDFONT CREATION ========")
    logger.info(f"Midi version: {run_settings.midi.midiversion}")

    # workbook = SoundfontWorkbook(midi_dict=midi_dict, preset_dict=preset_dict, settings=run_settings)
    sf_file = SoundfontTextfile(
        midi_dict=LOOKUP.INSTRUMENT_TO_MIDINOTE, preset_dict=LOOKUP.INSTRUMENT_TO_PRESET, settings=run_settings
    )
    sf_file.create_soundfont_definition()
    filepath = sf_file.save()
    logger.info(f"SoundFont definition saved to {filepath}")
    logger.info("=====================================")


def generate_sf2_with_viena(settings: RunSettings) -> None:
    """Creates and saves sf2 SoundFont files using Viena. Uses Keystrokes to execute Viena menu commands.
       Imports the SoundFont definition file and saves sf2 file(s) to the destination folder(s) in the run settings.

    Args:
        path_to_viena_app (str): _description_
        sf2_filepaths (list[str]): _description_
    """
    with subprocess.Popen(settings.soundfont.path_to_viena_app) as viena:
        time.sleep(3)
        pyautogui.hotkey("ctrl", "f4", interval=0.1)  # Close current file (if opened)
        pyautogui.hotkey("ctrl", "alt", "d", interval=0.1)  # Import definitions file
        pyautogui.write(os.path.abspath(settings.soundfont.def_filepath))  # Type full path in "File name" field.
        time.sleep(0.01)
        pyautogui.press("enter", interval=0.1)  # Import
        pyautogui.hotkey("enter", interval=0.1)  # Confirm create new SoundFont
        for outfilepath in settings.soundfont.sf_filepath_list:
            pyautogui.hotkey("shift", "ctrl", "s", interval=0.1)  # Save As ...
            pyautogui.press("tab", interval=0.1)  #
            pyautogui.press("tab", interval=0.1)  # Press tab twice to move cursor to File Name field.
            pyautogui.write(outfilepath)
            time.sleep(0.01)
            pyautogui.press("tab", interval=0.1)  # Focus to Save button
            pyautogui.press("enter", interval=0.1)  # Save
            pyautogui.press("y", interval=0.1)  # Answer Y to overwrite (no effect if file does not exist)
        viena.kill()


def create_soundfont_files(run_settings: RunSettings) -> None:
    """This method does all the work. Generates a soundfont definition file and creates sf2 files with the Viena application.

    Args:
        run_settings (RunSettings): _description_
    """
    create_soundfont_definition_file(run_settings)
    if run_settings.options.soundfont.create_sf2_files:
        generate_sf2_with_viena(run_settings)


if __name__ == "__main__":
    run_settings = get_run_settings()
    run_settings.options.soundfont.run = True
    create_soundfont_files(run_settings)
