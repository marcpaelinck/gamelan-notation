import os
import re
from dataclasses import dataclass, field
from typing import Any

import numpy as np
import pandas as pd
import yaml
from pydantic import BaseModel, ValidationError

from src.common.constants import InstrumentGroup
from src.common.logger import get_logger
from src.settings.classes import (
    Content,
    PartForm,
    RunSettings,
    SettingsData,
    SettingsInstrumentInfo,
    Song,
)
from src.settings.constants import DATA_INFOFILE, RUN_SETTINGSFILE, SETTINGSFOLDER, Yaml
from src.settings.utils import pretty_compact_json

logger = get_logger(__name__)

_RUN_SETTINGS: RunSettings = None
# List of functions that should be called when new run settings are loaded
_RUN_SETTINGS_LISTENERS: set[callable] = set()


# Contains information about where to find the data sources in the Value
DATA = {
    "instruments": {"category": "instruments", "folder": "folder", "filename": "instruments_file"},
    "instrument_tags": {"category": "instruments", "folder": "folder", "filename": "tags_file"},
    "rules": {"category": "instruments", "folder": "folder", "filename": "rules_file"},
    "midinotes": {"category": "midi", "folder": "folder", "filename": "midi_definition_file"},
    "presets": {"category": "midi", "folder": "folder", "filename": "presets_file"},
    "font": {"category": "font", "folder": "folder", "filename": "file"},
}


def post_process(subdict: dict[str, Any], run_settings_dict: dict[str, Any] = None, curr_path: list = []):
    """This function enables references to yaml key values using ${<yaml_path>} notation.
    e.g.: ${notations.defaults.include_in_production_run}
    The function substitutes these references with the corresponding yaml settings values.
    Does not (yet) implement usage of references within a list structure.

    Args:
        subdict (dict[str, Any]): Part of a yaml stucture in Python format for which to substitute references.
        run_settings_dict(dict[str, Any]): Full yaml structure in Python dict format.
    """
    found: re.Match

    for key, value in subdict.items():
        if isinstance(value, dict):
            # Iterate through dict structures until a root node is found
            sub_path = curr_path + [key]
            subdict[key] = post_process(value, run_settings_dict or subdict, sub_path)
        elif isinstance(value, str):
            # Only implemented for key: str items. Does not operate on list structures (yet)
            # Determine if a ${<yaml_path>} string ioccurs in the value.
            while found := re.search(r"\$\{\{(?P<item>[\w\.]+)\}\}", value):
                keys = found.group("item").split(".")
                # Replace '_PARENT_' literal with current path. Should be the first item in the list.
                if keys[0].upper() == "_PARENT_":
                    keys = curr_path + keys[1:]
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
        return yaml.load(settingsfile, yaml.Loader)


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
    notation_id = run_settings_dict[Yaml.NOTATION_ID]
    if not data_dict[Yaml.NOTATIONS].get(notation_id, None):
        logger.error(f"invalid composition name: {notation_id}")
        ok = False
    return ok


def load_run_settings(notation_id: str = None, part_id: str = None) -> RunSettings:
    """Retrieves the run settings from the run settings yaml file, enriched with information
       from the data information yaml file.

    Args:
        notation_id: key value of the notation as it appears in the data.yaml file
        part_id: key value of the part of the notation

    Returns:
        RunSettings: settings object
    """
    global _RUN_SETTINGS

    if not _RUN_SETTINGS:
        settings_data_dict = read_settings(DATA_INFOFILE)
        # update each notation entry with the default settings
        for key, notation_entry in settings_data_dict[Yaml.NOTATIONS].items():
            if key == Yaml.DEFAULTS:
                continue
            settings_data_dict[Yaml.NOTATIONS][key] = settings_data_dict[Yaml.NOTATIONS][Yaml.DEFAULTS] | notation_entry
        del settings_data_dict[Yaml.NOTATIONS][Yaml.DEFAULTS]
        settings_data_dict = post_process(settings_data_dict)

        run_settings_dict = read_settings(RUN_SETTINGSFILE)
        run_settings_dict[Yaml.SETTINGSDATA] = settings_data_dict
        run_settings_dict[Yaml.DATA] = read_data(settings_data_dict)

        try:
            # _SETTINGS_DATA = SettingsData.model_validate(settings_data_dict)
            _RUN_SETTINGS = RunSettings.model_validate(run_settings_dict)
        except ValidationError as e:
            # Aggregate errors by variable
            logger.error(str(e))
            exit()
    else:
        logger.info("Skipping reading of run settings")

    if notation_id and part_id:
        _RUN_SETTINGS.notation_id = notation_id
        _RUN_SETTINGS.part_id = part_id

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
    settings = load_run_settings("lengker", "full")
    print(settings.notation_id, settings.notation.part, settings.instrumentgroup)
