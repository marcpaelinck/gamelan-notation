"""
Functions for importing and validating the run settings.
"""

import os
import time
from typing import Callable

from src.common.constants import InstrumentGroup
from src.common.logger import Logging
from src.settings.classes import Content, PartForm, RunSettings, Song
from src.settings.utils import pretty_compact_json

# from src.settings.utils import pretty_compact_json

logger = Logging.get_logger(__name__)


class RunSettingsListener:
    """Subclassing this class will cause the subclass's `cls_initialize` method
    to be called each time new run settings are loaded"""

    def __init_subclass__(cls, **kwargs):
        Settings.add_run_settings_listener(cls.call_class_initializer)

    @classmethod
    def call_class_initializer(cls, run_settings: "RunSettings"):
        """wrapper for class initializer"""
        cls.cls_initialize(run_settings=run_settings)

    @classmethod
    def cls_initialize(cls, run_settings: "RunSettings"):
        """Override this method"""


class Settings:
    """Non-instantiable class. It holds a unique RunSettings instance that can be retrieved from any module."""

    # Unique instance of RunSettings
    RUN_SETTINGS: RunSettings = None

    # List of functions that should be called when new run settings are loaded
    RUN_SETTINGS_LISTENERS: set[callable] = set()

    @classmethod
    def get(cls, notation_id: str = None, part_id: str = None) -> RunSettings:
        """Returns RUN_SETTINGS. If either of the function's arguments notation_id or part_id is not None,
        the corresponding attribute of RUN_SETTINGS is set accordingly. if RUN_SETTINGS has not been
        assigned yet, a RunSettings object is created. In that case if notation_id and part_id are not given
        as arguments, the values are retrieved from the run-settings.yaml file.
        Args:
            notation_id, part_id (str): uniquely identify a notation file. The values should correspond with a key in
                                        config.yaml. If None, the values of RUN_SETTINGS remain unchanged.
        Returns:
            RunSettings: settings object
        """
        if cls.RUN_SETTINGS and not notation_id and not part_id:
            return cls.RUN_SETTINGS

        if not cls.RUN_SETTINGS:
            cls.RUN_SETTINGS = RunSettings()

        if notation_id:
            cls.RUN_SETTINGS.notation_id = notation_id
        if part_id:
            cls.RUN_SETTINGS.part_id = part_id

        logger.info(
            "Loading run settings for composition %s - %s",
            cls.RUN_SETTINGS.notation.title,
            cls.RUN_SETTINGS.notation.part.name,
        )

        for listener in cls.RUN_SETTINGS_LISTENERS:
            listener(cls.RUN_SETTINGS)

        return cls.RUN_SETTINGS

    @classmethod
    def add_run_settings_listener(cls, listener: Callable[[], None] = None) -> None:
        """Retrieves the most recently loaded run settings. Loads the settings from the run-settings.yaml file if no
        settings have been loaded yet.

        Args:
            listener (callable, optional): A function that should be called after new run settings have been loaded.
            This value can be passed by modules and objects that use the run settings during their (re-)initialization
            phase. Defaults to None.
        Returns:
            RunSettings: settings object
        """
        if listener:
            cls.RUN_SETTINGS_LISTENERS.add(listener)

    @classmethod
    def _temp_update_me(cls, content: Content):
        """Auxiliary function that updates the content with the pdf version"""
        # use only during development. #
        for song in content.songs:
            notation_info = next(
                (
                    notation
                    for key, notation in cls.RUN_SETTINGS.configdata.notations.items()
                    if notation.title == song.title
                ),
                None,
            )
            if song.pdf and notation_info:
                filepath = os.path.join(notation_info.folder_in, notation_info.parts["full"].file)
                modification_time = os.path.getmtime(filepath)
                version_date = time.strftime(
                    cls.RUN_SETTINGS.pdf_converter.version_fmt, time.gmtime(modification_time)
                ).lower()
                song.notation_version = version_date
        return content

    @classmethod
    def save_midiplayer_content(cls, playercontent: Content, datafolder: str, filename: str):
        """Saves the configuration file for the JavaScript midplayer app.
        Args:
            playercontent (Content): content that should be saved to the config file.
            filename (str, optional): name of the config file. Defaults to None.
        """
        contentfilepath = os.path.join(datafolder, filename)
        tempfilepath = os.path.join(datafolder, "_" + filename)
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

    @classmethod
    def get_midiplayer_content(cls, datafolder: str, filename: str) -> Content:
        """Loads the configuration file for the JavaScript midplayer app.
        Next to settings, the file contains information about the MIDI and PDF files
        in the app's production folder.
        Returns:
            Content: Structure for the midiplayer content.
        """
        with open(os.path.join(datafolder, filename), "r", encoding="utf-8") as filename:
            playercontent = filename.read()
        # return temp_update_me(Content.model_validate_json(playercontent))
        return Content.model_validate_json(playercontent)

    @classmethod
    def update_midiplayer_content(
        cls,
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
        run_settings = RunSettings()
        content = cls.get_midiplayer_content(run_settings.midiplayer.folder, run_settings.midiplayer.contentfile)
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
        if notation_version:
            player_song.notation_version = notation_version

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
                    # pylint gets confused by Pydantic Field() assignment to Song.part in Song class definition.
                    player_song.parts.append(partinfo)  # pylint: disable=no-member
                    logger.info("New part %s created for MIDI player content", partinfo.part)
                else:
                    logger.error(
                        "Can't add new part info '%s' to the midiplayer content: missing midifile information. "
                        "Please run again with run-option `save_midifile` set.",
                        partinfo.part,
                    )
        cls.save_midiplayer_content(content, run_settings.midiplayer.folder, run_settings.midiplayer.contentfile)


if __name__ == "__main__":
    # For testing
    settings = Settings.get("godekmiring", "kawitan")
    print(settings.notation)
