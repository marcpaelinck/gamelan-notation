"""
Functions for importing and validating the run settings.
"""

import os
import re
import time
from typing import Any, Callable

import numpy as np
import pandas as pd
import yaml
from pydantic import BaseModel, ValidationError

from src.common.constants import (
    InstrumentGroup,
    InstrumentType,
    Modifier,
    Pitch,
    Position,
    RuleParameter,
    RuleType,
    RuleValue,
    Stroke,
)
from src.common.logger import get_logger
from src.settings.classes import Content, PartForm, RunSettings, Song
from src.settings.constants import CONFIG_FILE, RUN_SETTINGSFILE, SETTINGSFOLDER, Yaml
from src.settings.utils import pretty_compact_json

logger = get_logger(__name__)

# Container for the run settings
_RUN_SETTINGS: RunSettings = None
# List of functions that should be called when new run settings are loaded
_RUN_SETTINGS_LISTENERS: set[callable] = set()


# DATA contains information about the location of the data sources and how to format the content.
# The values of the first three entries (section, folder and location) refer to key values in the config file.
# Structure:
# <table-key>: {"section": <top level key>, "folder": <key of data subfolder>, "filename": <key of file name>}
# table-name is the target key in the `data` section of the settings dict
# The "formats" member contains information for the formatting to apply on each individual record. The tuple items
# have the following meaning (the last item is optional).
#   #0: <list of NotationEnum sublasses>: classes to include when applying the eval function to the string value.
#   #1: <default value> to be applied instead of the eval function if the value an empty string or missing.
#   #2: <post-processing function>. Applied after the above transformations. It should have the entire record as
#     only argument.
# For numerical values, the first member should be an empty list.
# Any non-formatted field will have a str format.
DATA = {
    "instruments": {
        "section": "instruments",
        "folder": "folder",
        "filename": "instruments_file",
        "formats": {
            "group": ([InstrumentGroup], None),
            "position": ([Position], None),
            "instrumenttype": ([InstrumentType], None),
            "position_range": ([Pitch], []),
            "extended_position_range": ([Pitch], []),
        },
    },
    "instrument_tags": {
        "section": "instruments",
        "folder": "folder",
        "filename": "tags_file",
        "formats": {
            "groups": ([InstrumentGroup], None),
            "positions": ([Position, RuleValue], None),
        },
    },
    "rules": {
        "section": "instruments",
        "folder": "folder",
        "filename": "rules_file",
        "formats": {
            "group": ([InstrumentGroup], None),
            "ruletype": ([RuleType], None),
            "positions": ([Position, RuleValue], None),
            "parameter1": ([RuleParameter], []),
            "value1": ([RuleValue, Pitch, Position], []),
            "parameter2": ([RuleParameter], []),
            "value2": ([RuleValue], []),
        },
    },
    "midinotes": {
        "section": "midi",
        "folder": "folder",
        "filename": "midi_definition_file",
        "formats": {
            "instrumentgroup": ([InstrumentGroup], None),
            "instrumenttype": ([InstrumentType], None),
            "positions": (
                [Position],
                None,
                lambda record: (
                    [p for p in Position if p.instrumenttype == record["instrumenttype"]]
                    if not record["positions"]
                    else record["positions"]
                ),
            ),
            "pitch": ([Pitch], Pitch.NONE),
            "octave": ([], None),
            "stroke": ([Stroke], Stroke.NONE),
            "midinote": (
                [],
                [],
                lambda record: record["midinote"] if isinstance(record["midinote"], list) else [record["midinote"]],
            ),
        },
    },
    "presets": {
        "section": "midi",
        "folder": "folder",
        "filename": "presets_file",
        "formats": {
            "instrumentgroup": ([InstrumentGroup], None),
            "instrumenttype": ([InstrumentType], None),
            "position": ([Position], None),
            "bank": ([], None),
            "preset": ([], None),
            "channel": ([], None),
            "port": ([], None),
        },
    },
    "font": {
        "section": "font",
        "folder": "folder",
        "filename": "file",
        "formats": {
            "pitch": ([Pitch], Pitch.NONE),
            "octave": ([], None),
            "stroke": ([Stroke], Stroke.NONE),
            "duration": ([], None),
            "rest_after": ([], None),
            "modifier": ([Modifier], Modifier.NONE),
        },
    },
}


def post_process(subdict: dict[str, Any], run_settings_dict: dict[str, Any] = None, curr_path: list = None):
    """This function enables references to yaml key values using ${<yaml_path>} notation.
    e.g.: ${notations.defaults.include_in_production_run}
    The function substitutes these references with the corresponding yaml settings values.
    Does not (yet) implement usage of references within a list structure.

    Args:
        subdict (dict[str, Any]): Part of a yaml stucture in Python format for which to substitute references.
        run_settings_dict(dict[str, Any]): Full yaml structure in Python dict format.
    """
    found: re.Match
    curr_path = curr_path or []

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
            subdict[key] = value
    return subdict


def read_settings(filename: str) -> dict:
    """Retrieves settings from the given (YAML) file. The file should occur in SETTINGSFOLDER.

    Args:
        filename (str): YAML file name. Should occur in SETTINGSFOLDER.

    Returns:
        dict: dict containing all the settings contained in the file.
    """
    with open(os.path.join(SETTINGSFOLDER, filename), "r", encoding="utf-8") as settingsfile:
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


def read_data(settings_dict: dict, specs: dict) -> dict[str, list[dict[str, str]]]:
    """Reads multiple data files into table-like dict structures. Columns that appear in the 'format' section
       of the specs will be formatted accordingly.
    Args:
        settings_dict (dict): dict containing run settings
        specs: (dict): dict containing information about the data to retrieve.
               The values refer to keys in the settings dict. Format:
            {<table1-key>:
                {"section": <top level key>, "folder": <key of data subfolder>, "filename": <key of file name>, "formats" : <formatting>},
            <table2-key>: ...
            }
            where <formatting> is a tuple (list[<NotationEnum class>], <value if missing or none>)
    Returns:
        dict[str, list[dict[str, str]]]: dict table-key -> <list of records> where each record represents a row.
    """
    data = dict()
    for item, entry in specs.items():
        category = entry["section"]
        folder = settings_dict[category][entry["folder"]]
        file = settings_dict[category][entry["filename"]]
        filepath = os.path.join(folder, file)
        data[item] = (
            pd.read_csv(filepath, sep="\t", comment="#", dtype=str)
            .replace([np.nan], [""], regex=False)
            .to_dict(orient="records")
        )
        if "formats" in entry:
            for fmtcolumn, formatting in entry["formats"].items():
                for record in data[item]:
                    if fmtcolumn in record:
                        if not record[fmtcolumn]:
                            # format missing value
                            record[fmtcolumn] = formatting[1]
                        else:
                            mapping = {strval: val for fmt in formatting[0] for strval, val in fmt.member_map().items()}
                            record[fmtcolumn] = eval(record[fmtcolumn] or formatting[1], mapping)
                        # Apply formatting function if available
                        if len(formatting) > 2:
                            record[fmtcolumn] = formatting[2](record)
    return data


def get_run_settings(listener: Callable[[], None] = None) -> RunSettings:
    """Retrieves the most recently loaded run settings. Loads the settings from the run-settings.yaml file if no
    settings have been loaded yet.

    Args:
        listener (callable, optional): A function that should be called after new run settings have been loaded.
        This value can be passed by modules and objects that use the run settings during their (re-)initialization
        phase. Defaults to None.
    Returns:
        RunSettings: settings object
    """
    if not _RUN_SETTINGS:
        load_run_settings()
    if listener:
        _RUN_SETTINGS_LISTENERS.add(listener)

    return _RUN_SETTINGS


def validate_settings(data_dict: dict, run_settings_dict: dict) -> bool:
    """Checks that the notation id and part id correspond with an entry in the config file (config.yaml).
    Args:
        data_dict (dict): _description_
        run_settings_dict (dict): _description_
    Returns:
        bool: _description_
    """
    notation_id = run_settings_dict[Yaml.NOTATION_ID]
    part_id = run_settings_dict[Yaml.PART_ID]
    if not data_dict[Yaml.NOTATIONS].get(notation_id, None):
        logger.error("Invalid composition name: %s", notation_id)
        return False
    if not data_dict[Yaml.NOTATIONS][Yaml.NOTATION_ID].get(part_id, None):
        logger.error("Part %s not found in composition %s", part_id, notation_id)
        return False
    return True


def load_run_settings(notation_id: str = None, part_id: str = None) -> RunSettings:
    """Retrieves the run settings from the run settings yaml file, enriched with information
       from the data information yaml file.
       Be aware that this method is called automatically when python first encounters an import statement that imports
       src.common.classes (see the `_build_class` methods in that module). This is especially relevant for unit tests
       that use separate YAML settings files.

    Args:
        notation_id: key value of the notation as it appears in the config.yaml file
        part_id: key value of the part of the notation

    Returns:
        RunSettings: settings object
    """
    global _RUN_SETTINGS  # pylint: disable=global-statement

    if not _RUN_SETTINGS:
        settings_data_dict = read_settings(CONFIG_FILE)
        # update each notation entry with the default settings
        for key, notation_entry in settings_data_dict[Yaml.NOTATIONS].items():
            if key == Yaml.DEFAULTS:
                continue
            settings_data_dict[Yaml.NOTATIONS][key] = settings_data_dict[Yaml.NOTATIONS][Yaml.DEFAULTS] | notation_entry
        del settings_data_dict[Yaml.NOTATIONS][Yaml.DEFAULTS]
        settings_data_dict = post_process(settings_data_dict)

        run_settings_dict = read_settings(RUN_SETTINGSFILE)
        run_settings_dict[Yaml.SETTINGSDATA] = settings_data_dict
        run_settings_dict[Yaml.DATA] = read_data(settings_data_dict, DATA)

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


def temp_update_me(content: Content):
    """Auxiliary function that updates the content with the pdf version"""
    for song in content.songs:
        notation_info = next(
            (
                notation
                for key, notation in _RUN_SETTINGS.settingsdata.notations.items()
                if notation.title == song.title
            ),
            None,
        )
        if song.pdf and notation_info:
            filepath = os.path.join(notation_info.folder_in, notation_info.parts["full"].file)
            modification_time = os.path.getmtime(filepath)
            version_date = time.strftime("%d-%b-%Y", time.gmtime(modification_time)).lower()
            song.notation_version = version_date
    return content


def get_midiplayer_content() -> Content:
    """Loads the configuration file for the JavaScript midplayer app.
       Next to settings, the file contains information about the MIDI and PDF files
       in the app's production folder.
    Returns:
        Content: Structure for the midiplayer content.
    """
    run_settings = _RUN_SETTINGS
    datafolder = run_settings.midiplayer.folder
    contentfile = run_settings.midiplayer.contentfile
    with open(os.path.join(datafolder, contentfile), "r", encoding="utf-8") as contentfile:
        playercontent = contentfile.read()
    # return temp_update_me(Content.model_validate_json(playercontent))
    return Content.model_validate_json(playercontent)


def save_midiplayer_content(playercontent: Content, filename: str = None):
    """Saves the configuration file for the JavaScript midplayer app.
    Args:
        playercontent (Content): content that should be saved to the config file.
        filename (str, optional): name of the config file. Defaults to None.
    """
    run_settings = _RUN_SETTINGS
    datafolder = run_settings.midiplayer.folder
    contentfile = filename or run_settings.midiplayer.contentfile
    contentfilepath = os.path.join(datafolder, contentfile)
    tempfilepath = os.path.join(datafolder, "_" + contentfile)
    try:
        with open(tempfilepath, "w", encoding="utf-8") as outfile:
            jsonised = pretty_compact_json(playercontent.model_dump())
            outfile.write(jsonised)
    except IOError as e:
        os.remove(tempfilepath)
        logger.error(e)
    else:
        os.remove(contentfilepath)
        os.rename(tempfilepath, contentfilepath)


def update_midiplayer_content(
    title: str,
    group: InstrumentGroup,
    partinfo: PartForm | None = None,
    pdf_file: str | None = None,
    notation_version: str = "",
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
        content.songs.append(
            player_song := Song(
                title=title, instrumentgroup=group, display=True, pfd=pdf_file, notation_version=notation_version
            )
        )
        logger.info("New song %s created for MIDI player content", player_song.title)
    elif pdf_file:
        player_song.pdf = pdf_file

    if partinfo:
        # pylint: disable=not-an-iterable
        # pylint gets confused by assignment of Field() to Pydantic member Song.parts
        part = next((part_ for part_ in player_song.parts if part_.part == partinfo.part), None)
        if part:
            part.file = partinfo.file or part.file
            part.loop = partinfo.loop or part.loop
            part.markers = partinfo.markers or part.markers
            logger.info("Existing part %s updated for MIDI player content", part.part)
        else:
            if partinfo.file:
                # pylint: disable=no-member
                # pylint gets confused by assignment of Field() to Pydantic member Song.parts
                player_song.parts.append(partinfo)
                logger.info("New part %s created for MIDI player content", partinfo.part)
            else:
                logger.error(
                    "Can't add new part info '%s' to the midiplayer content: missing midifile information. "
                    "Please run again with run-option `save_midifile` set.",
                    partinfo.part,
                )
    save_midiplayer_content(content)


if __name__ == "__main__":
    # For testing
    settings = load_run_settings("lengker", "full")
    print(settings.notation_id, settings.notation.part, settings.instrumentgroup)
