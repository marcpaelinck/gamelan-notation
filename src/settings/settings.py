"""
Functions for importing and validating the run settings.
"""

from typing import Callable

from src.common.logger import Logging
from src.settings.classes import RunSettings

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


if __name__ == "__main__":
    # For testing
    settings = Settings.get("godekmiring", "kawitan")
    print(settings.notation_version)
