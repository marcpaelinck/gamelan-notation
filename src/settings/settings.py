import os
import re
from typing import Any

import numpy as np
import pandas as pd
import yaml
from pydantic import BaseModel, ValidationError

from src.common.constants import InstrumentGroup
from src.common.logger import get_logger
from src.settings.classes import Content, PartForm, RunSettings, Song
from src.settings.constants import (
    DATA_INFOFILE,
    RUN_SETTINGSFILE,
    SETTINGSFOLDER,
    TEST_SETTINGSFOLDER,
    Yaml,
)
from src.settings.utils import pretty_compact_json

logger = get_logger(__name__)

_RUN_SETTINGS: RunSettings = None
# List of functions that should be called when new run settings are loaded
_RUN_SETTINGS_LISTENERS: set[callable] = set()


# Contains information about where to find the data sources in the Value
DATA = {
    "font": {"category": "font", "folder": "folder", "filename": "file"},
    "instruments": {"category": "instruments", "folder": "folder", "filename": "instruments_file"},
    "instrument_tags": {"category": "instruments", "folder": "folder", "filename": "tags_file"},
    "rules": {"category": "instruments", "folder": "folder", "filename": "rules_file"},
    "midinotes": {"category": "midi", "folder": "folder", "filename": "midi_definition_file"},
    "presets": {"category": "midi", "folder": "folder", "filename": "presets_file"},
}


def post_process(subdict: dict[str, Any], run_settings_dict: dict[str, Any] = None):
    """This function enables references to yaml key values using ${<yaml_path>} notation.
    The function substitutes these values with the corresponding yaml settings values.
    Does not (yet) implement usage of references within a list structure.

    Args:
        subdict (dict[str, Any]): Part of a yaml stucture in Python format.
        run_settings_dict(dict[str, Any]): Full yaml structure in Python dict format.
    """
    found: re.Match

    for key, value in subdict.items():
        if isinstance(value, dict):
            # Iterate through dict structures until a root node is found
            subdict[key] = post_process(value, run_settings_dict or subdict)
        elif isinstance(value, str):
            # Only implemented for key: str items. Does not operate on list structures (yet)
            while found := re.search(r"\$\{(?P<item>[\w\.]+)\}", value):
                keys = found.group("item").split(".")
                item = run_settings_dict
                for key1 in keys:
                    item = item[key1]
                if found.group(0) == value:
                    # Value is a reference to a key value.
                    value = item
                    break
                else:
                    # Value is a string containing one or more ${...} references.
                    # Substitute the sub-expression in the string.
                    value = value.replace(found.group(0), item)
                i = 1
            subdict[key] = value
    return subdict


def get_cwd():
    return os.getcwd()


def read_settings(filename: str) -> dict:
    """Retrieves settings from the given (YAML) file. The file should occur in SETTINGSFOLDER.

    Args:
        filename (str): YAML file name. Should occur in SETTINGSFOLDER.

    Returns:
        dict: dict containing all the settings contained in the file.
    """
    with open(os.path.join(SETTINGSFOLDER, filename), "r") as settingsfile:
        return yaml.load(settingsfile, Loader=yaml.SafeLoader)


def get_settings_fields(cls: BaseModel, settings_dict: dict) -> dict[str, Any]:
    """Retrieves all the fields from run_settings_dict and data_dict that match the field names of cls.

    Args:
        cls (BaseModel): Pydantic class for which to retrieve the fields
        settings_dict (dict): Dict containing settings fields

    Returns:
        dict[str, Any]: _description_
    """
    retval = {key: settings_dict[key] for key in cls.model_fields.keys() if key in settings_dict}
    return retval


def read_data(settings_dict: dict) -> dict[str, list[dict[str, str]]]:
    data = dict()
    for item, entry in DATA.items():
        category = entry["category"]
        folder = settings_dict[category][entry["folder"]]
        file = settings_dict[category][entry["filename"]]
        filepath = os.path.join(folder, file)
        data[item] = (
            pd.read_csv(filepath, sep="\t", comment="#", dtype=str)
            .replace([np.nan], [""], regex=False)
            .to_dict(orient="records")
        )
    return data


def get_run_settings(listener: callable = None) -> RunSettings:
    """Retrieves the most recently loaded run settings. Loads the settings from the run-settings.yaml file if no
    settings have been loaded yet.
    Be aware that the run settings are loaded at the first import of src.common.classes. If you need to load settings
    from another location than the default folder set in src.settings.constants, (e.g. for unit tests), you will need
    to call load_run_settings after having changed the folder.

    Args:
        listener (callable, optional): A function that should be called when new run settings are loaded. This value
        can be passed by modules and objects that use the run settings during their initialization phase. Defaults to None.

    Returns:
        RunSettings: settings object
    """
    if not _RUN_SETTINGS:
        load_run_settings()
    if listener:
        _RUN_SETTINGS_LISTENERS.add(listener)

    return _RUN_SETTINGS


def validate_settings(data_dict: dict, run_settings_dict: dict) -> bool:
    ok = True
    composition = run_settings_dict[Yaml.NOTATION][Yaml.COMPOSITION]
    if not data_dict[Yaml.NOTATIONS].get(composition, None):
        logger.error(f"invalid composition name: {composition}")
        ok = False
    return ok


def load_run_settings(notation: dict[str, str] = None) -> RunSettings:
    """Retrieves the run settings from the run settings yaml file, enriched with information
       from the data information yaml file.

    Args:
        notation (dict[str, str], optional): A dict {'composition': <composition>, 'part': <part>} that defines a
        composition/part combination in the data.yaml file. Defaults to the values in the run-settings.yaml file.

    Returns:
        RunSettings: settings object
    """
    run_settings_dict = read_settings(RUN_SETTINGSFILE)
    data_dict = read_settings(DATA_INFOFILE)

    # Validate some manually set settings and abort if invalid
    if not validate_settings(data_dict, run_settings_dict):
        exit()

    settings_dict = dict()

    # Run Options
    settings_dict[Yaml.OPTIONS] = get_settings_fields(RunSettings.Options, run_settings_dict[Yaml.OPTIONS])

    # MIDI info
    midiversion = data_dict[Yaml.MIDI][Yaml.MIDIVERSIONS][run_settings_dict[Yaml.MIDI][Yaml.MIDIVERSION]]
    settings_dict[Yaml.MIDI] = get_settings_fields(
        RunSettings.MidiInfo, data_dict[Yaml.MIDI] | run_settings_dict[Yaml.MIDI] | midiversion
    )

    # # Sample info
    # samples = data_dict[Yaml.SAMPLES][Yaml.INSTRUMENTGROUPS][run_settings_dict[Yaml.SAMPLES][Yaml.INSTRUMENTGROUP]]
    # settings_dict[Yaml.SAMPLES] = get_settings_fields(
    #     RunSettings.SampleInfo, samples | run_settings_dict[Yaml.SAMPLES] | data_dict[Yaml.SAMPLES]
    # )

    # # Soundfont info
    # settings_dict[Yaml.SOUNDFONT] = get_settings_fields(
    #     RunSettings.SoundfontInfo, data_dict[Yaml.SOUNDFONTS] | run_settings_dict[Yaml.SOUNDFONT]
    # )

    settings_dict[Yaml.MIDIPLAYER] = get_settings_fields(RunSettings.MidiPlayerInfo, data_dict[Yaml.MIDIPLAYER])

    # NOTATION INFORMATION

    # Add the list of all notations and update each entry with the default settings
    settings_dict[Yaml.NOTATIONS] = data_dict[Yaml.NOTATIONS]
    for key, notation_entry in settings_dict[Yaml.NOTATIONS].items():
        if key == Yaml.DEFAULTS:
            continue
        settings_dict[Yaml.NOTATIONS][key] = data_dict[Yaml.NOTATIONS][Yaml.DEFAULTS] | notation_entry
    del settings_dict[Yaml.NOTATIONS][Yaml.DEFAULTS]

    if notation:
        run_settings_dict[Yaml.NOTATION] = notation

    notation = data_dict[Yaml.NOTATIONS][run_settings_dict[Yaml.NOTATION][Yaml.COMPOSITION]]
    notation[Yaml.PART_ID] = run_settings_dict[Yaml.NOTATION][Yaml.PART_ID]

    settings_dict[Yaml.NOTATION] = get_settings_fields(
        RunSettings.NotationInfo,
        notation,
    )

    # INSTRUMENT INFORMATION

    instruments = data_dict[Yaml.INSTRUMENTS][Yaml.INSTRUMENTGROUPS][notation[Yaml.INSTRUMENTGROUP]]
    settings_dict[Yaml.INSTRUMENTS] = get_settings_fields(
        RunSettings.InstrumentInfo,
        notation | data_dict[Yaml.INSTRUMENTS] | instruments,
    )

    # FONT INFORMATION

    font = data_dict[Yaml.FONTS][Yaml.FONTVERSIONS][notation[Yaml.FONTVERSION]] | {
        Yaml.FONTVERSION: notation[Yaml.FONTVERSION]
    }
    settings_dict[Yaml.FONT] = get_settings_fields(RunSettings.FontInfo, data_dict[Yaml.FONTS] | font)

    # GRAMMAR INFORMATION

    fontgrammar = data_dict[Yaml.GRAMMARS][Yaml.FONTVERSIONS][notation[Yaml.FONTVERSION]]
    settings_dict[Yaml.GRAMMARS] = get_settings_fields(RunSettings.GrammarInfo, data_dict[Yaml.GRAMMARS] | fontgrammar)

    # SETTINGS FOR THE PDF OUTPUT GENERATOR

    settings_dict[Yaml.PDF_CONVERTER] = get_settings_fields(RunSettings.PdfConverterInfo, data_dict[Yaml.PDF_CONVERTER])

    # # MULTIPLE RUNS INTEGRATION TEST INFORMATION

    # run_option = run_settings_dict[Yaml.OPTIONS][Yaml.NOTATION_TO_MIDI][Yaml.RUNTYPE]
    # if run_option != Yaml.RUN_SINGLE:
    #     settings_dict[Yaml.MULTIPLE_RUNS] = get_settings_fields(
    #         RunSettings.MultipleRunsInfo, data_dict[Yaml.MULTIPLE_RUNS][run_option]
    #     )

    settings_dict = post_process(settings_dict)

    # DATA FILES

    settings_dict[Yaml.DATA] = read_data(settings_dict)

    global _RUN_SETTINGS
    try:
        _RUN_SETTINGS = RunSettings.model_validate(settings_dict)
    except ValidationError as e:
        # Aggregate errors by variable
        errors = {err["input"]: err["msg"] for err in e.errors()}
        logger.error(errors)
        exit()

    for listener in _RUN_SETTINGS_LISTENERS:
        listener(_RUN_SETTINGS)
    return get_run_settings()


def get_all_notation_parts(include_tests: bool = False) -> dict[str, str]:
    data_dict = read_settings(DATA_INFOFILE)
    return [
        {Yaml.COMPOSITION: n, Yaml.PART_ID: p}
        for n in data_dict[Yaml.NOTATIONS].keys()
        if not n.startswith("default") and (include_tests or not n.startswith("test"))
        for p in data_dict[Yaml.NOTATIONS][n][Yaml.PART_ID].keys()
    ]


def get_midiplayer_content() -> Content:
    run_settings = _RUN_SETTINGS
    datafolder = run_settings.midiplayer.folder
    contentfile = run_settings.midiplayer.contentfile
    with open(os.path.join(datafolder, contentfile), "r") as contentfile:
        playercontent = contentfile.read()
    return Content.model_validate_json(playercontent)


def save_midiplayer_content(playercontent: Content, filename: str = None):
    run_settings = _RUN_SETTINGS
    datafolder = run_settings.midiplayer.folder
    contentfile = filename or run_settings.midiplayer.contentfile
    contentfilepath = os.path.join(datafolder, contentfile)
    tempfilepath = os.path.join(datafolder, "_" + contentfile)
    try:
        with open(tempfilepath, "w") as outfile:
            jsonised = pretty_compact_json(playercontent.model_dump())
            outfile.write(jsonised)
    except Exception as e:
        os.remove(tempfilepath)
        logger.error(e)
    else:
        os.remove(contentfilepath)
        os.rename(tempfilepath, contentfilepath)


def update_midiplayer_content(
    title: str, group: InstrumentGroup, partinfo: PartForm | None = None, pdf_file: str | None = None
) -> None:
    """Updates the information given in Part in the content.json file of the midi player.

    Args:
        title (str): Title of the `song`, should be taken from run_settings.notation.title.
        group (InstrumentGroup):
        part (Part): Information that should be stored/updated. Attributes of `part` equal to None
                     will not be modified in contents.json.
    """
    content = get_midiplayer_content()
    # If info is already present, replace it.
    player_song: Song = next((song_ for song_ in content.songs if song_.title == title), None)
    if not player_song:
        # TODO create components of Song
        content.songs.append(player_song := Song(title=title, instrumentgroup=group, display=True, pfd=pdf_file))
        logger.info(f"New song {player_song.title} created for MIDI player content")
    elif pdf_file:
        player_song.pdf = pdf_file

    if partinfo:
        part = next((part_ for part_ in player_song.parts if part_.part == partinfo.part), None)
        if part:
            part.file = partinfo.file or part.file
            part.loop = partinfo.loop or part.loop
            part.markers = partinfo.markers or part.markers
            logger.info(f"Existing part {part.part} updated for MIDI player content")
        else:
            if partinfo.file:
                player_song.parts.append(partinfo)
                logger.info(f"New part {partinfo.part} created for MIDI player content")
            else:
                logger.error(
                    f"Can't add new part info '{partinfo.part}' to the midiplayer content: missing midifile information. Please run again with run-option `save_midifile` set."
                )
    save_midiplayer_content(content)


if __name__ == "__main__":
    # For testing
    settings = get_run_settings()
    print(settings.font)
