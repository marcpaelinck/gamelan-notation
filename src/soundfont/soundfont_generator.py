""" Creates an Excel soundfont definition file. This file can imported in the Viena application 
    to create a  Soundfont file (.sf2 format). See http://www.synthfont.com/The_Definitions_File.pdf

    Main method: create_soundfont_file()
"""

from src.common.classes import RunSettings
from src.common.logger import get_logger
from src.common.lookups import MIDINOTE_LOOKUP, PRESET_LOOKUP
from src.common.utils import initialize_lookups
from src.soundfont.soundfont_textfile import SoundfontTextfile
from src.soundfont.soundfont_workbook import SoundfontWorkbook

logger = get_logger(__name__)


def create_soundfont_file(run_settings: RunSettings):
    """This method does all the work.
    All settings are read from the (YAML) settings files.
    """
    logger.info("======== SOUNDFONT CREATION ========")
    logger.info(f"input file: {run_settings.soundfont.sheetname}")
    initialize_lookups(run_settings)

    # workbook = SoundfontWorkbook(midi_dict=midi_dict, preset_dict=preset_dict, settings=run_settings)
    sf_file = SoundfontTextfile(midi_dict=MIDINOTE_LOOKUP, preset_dict=PRESET_LOOKUP, settings=run_settings)
    sf_file.create_soundfont_definition()
    filepath = sf_file.save()
    logger.info(f"SoundFont definition saved to {filepath}")
    logger.info("=====================================")


if __name__ == "__main__":
    ...
