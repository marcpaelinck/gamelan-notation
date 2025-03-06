# BASE CLASS FOR THE CLASSES THAT PERFORM THE NOTATION -> MIDI CONVERSION


import logging
from enum import StrEnum
from typing import Any, Callable, Generator

from src.common.classes import Beat
from src.common.constants import Position
from src.common.logger import get_logger
from src.settings.classes import RunSettings


class NamedIntID(int):
    # To be used by notation parser, for better readability of the output dict.
    # The class formats int values with meaningful names.
    # When subclassing this class, change the `name`and optionally the `default` value.
    name = "NamedID"
    default = "DEFAULT"
    default_value = -1
    nbr_format = "d"

    def __init__(self, value: int):
        if isinstance(value, str) and value.isnumeric():
            self.value = int(value)
        elif isinstance(value, int):
            self.value = value
        else:
            raise ValueError(f"illegal value {value}.")
        if value >= 0:
            self.repr = self.name + f"({{value:{self.nbr_format}}})".format(value=self.value)
        else:
            self.repr = self.default + f"({{value:{self.nbr_format}}})".format(value=self.value)

    def __repr__(self):
        return self.repr


class ParserModel:
    # Base class for the classes that each perform a step of the conversion
    # from notation to MIDI/PDF/TXT output. It provides a uniform logging format.
    class ParserType(StrEnum):
        # Used by the logger to determine the source of a warning or error
        # message.
        SETTINGSVALIDATOR = "VALIDATING RUN SETTINGS"
        NOTATIONPARSER = "PARSING NOTATION TO DICT"
        SCOREGENERATOR = "CONVERTING DICT TO SCORE"
        VALIDATOR = "VALIDATING SCORE"
        MIDIGENERATOR = "GENERATING MIDI FILE"
        SCORETOPDF = "CONVERTING SCORE TO PDF NOTATION"

    parser_type: ParserType
    run_settings = None
    curr_gongan_id: int = None
    curr_beat_id: int = None
    curr_position: Position = None
    curr_line_nr: int = None
    log_msgs: dict[int, str] = {logging.ERROR: [], logging.WARNING: []}
    logger = None

    def __init__(self, parser_type: ParserType, run_settings: RunSettings):
        self.parser_type = parser_type
        self.run_settings = run_settings
        self.logger = get_logger(self.__class__.__name__)

    @classmethod
    def main(cls, func: Callable):
        """Decorator for main parser function. Add a @ParserModel.main decorator
        to the main method of each subclass. This will take care of
        of logging before the start and after the end of the method."""

        def wrapper(*args, **kwargs):
            self = args[0]
            separator = "=" * int(50 - len(self.parser_type.value) // 2)
            title = f"{separator} {self.parser_type.value} {separator}"
            self.logger.info(title)

            result = func(*args, **kwargs)

            sep_length = len(title)
            self.logger.info("=" * sep_length)
            return result

        return wrapper

    def _close_logging(self):
        self.logger.info("=" * 102)

    def f(self, val: int | None, pos: int):
        # Number formatting
        p = f"{pos:02d}"
        return f"{val:{p}d}" if val else " " * pos

    def log(self, msg: str, *args, level: int = logging.ERROR) -> str:
        """Formats the message. and sends it to the console. Stores a copy in the log_msgs dict.
        Args:
            msg (str): The message
            level (int, optional): Logging level. Defaults to logging.ERROR.
            *args: optional arguments for the logger (required when lazy % formatting is applied).
        Returns:
            str: _description_
        """
        extra_spaces = " " * (7 - len(logging.getLevelName(level)))
        prefix = f"{extra_spaces}{self.f(self.curr_gongan_id,2)}-{self.f(self.curr_beat_id,2)} |{self.f(self.curr_line_nr,4)}| "
        msg = prefix + msg
        self.logger.log(level, msg, *args)
        if level > logging.INFO:
            self.log_msgs[level].append(msg)

    def logerror(self, msg: str, *args: Any) -> str:
        """Logs an error"""
        self.log(msg, *args, level=logging.ERROR)

    def logwarning(self, msg: str, *args: Any) -> str:
        """Logs a warning"""
        self.log(msg, *args, level=logging.WARNING)

    def loginfo(self, msg: str, *args: Any) -> str:
        """Logs info"""
        self.log(msg, *args, level=logging.INFO)

    # Use the following generators to iterate through gongans and beats if you
    # want to use the logging methods of this class. This will ensure that the
    # logging is prefixed with the correct gongan id, beat id and line number.

    def gongan_iterator(self, obj: Any):
        if not hasattr(obj, "gongans"):
            raise AttributeError("base object has no attribute `gongans`")
        for gongan in obj.gongans:
            self.curr_gongan_id = gongan.id
            self.curr_beat_id = None
            yield gongan

    def beat_iterator(self, obj: Any) -> Generator[Beat, None, None]:
        if not hasattr(obj, "beats"):
            raise AttributeError("base object has no attribute `beats`")
        for beat in obj.beats:
            self.curr_beat_id = beat.id
            yield beat

    def pass_iterator(self, obj: Any):
        if not hasattr(obj, "passes"):
            raise AttributeError("base object has no attribute `passes`")
        for _, pass_seq in obj.passes.items():
            self.curr_line_nr = pass_seq.line
            yield pass_seq

    @property
    def has_errors(self):
        return len(self.log_msgs[logging.ERROR]) > 0

    @property
    def has_warnings(self):
        return len(self.log_msgs[logging.WARNING]) > 0
