# BASE CLASS FOR THE CLASSES THAT PERFORM THE NOTATION -> MIDI CONVERSION


import logging
from enum import StrEnum
from typing import Any

from src.common.constants import Position
from src.common.logger import get_logger
from src.settings.classes import RunSettings


class ParserModel:
    # Base class for the classes that each perform a step of the conversion
    # from notation to MIDI output. It provides a uniform logging format.
    class ParserType(StrEnum):
        # Used by the logger to determine the source of a warning or error
        # message.
        NOTATIONPARSER = "parsing the notation"
        SCOREGENERATOR = "generating the score"
        VALIDATOR = "validating the score"
        MIDIGENERATOR = "generating the midi file"

    parser_type: ParserType
    run_settings = None
    curr_gongan_id: int = None
    curr_beat_id: int = None
    curr_position: Position = None
    curr_line_nr: int = None
    errors = []
    logger = None

    def __init__(self, parser_type: ParserType, run_settings: RunSettings):
        self.parser_type = parser_type
        self.run_settings = run_settings
        self.logger = get_logger(self.__class__.__name__)

    def f(self, val: int | None, pos: int):
        # Number formatting
        p = f"{pos:02d}"
        return f"{val:{p}d}" if val else " " * pos

    def log(self, err_msg: str, level: logging = logging.ERROR) -> str:
        prefix = f"{self.f(self.curr_gongan_id,2)}-{self.f(self.curr_beat_id,2)} |{self.f(self.curr_line_nr,4)}| "
        if level > logging.INFO and not self.errors:
            self.logger.error(f"ERRORS ENCOUNTERED WHILE {self.parser_type.value.upper()}:")
        msg = prefix + err_msg
        self.logger.log(level, msg)
        if level > logging.INFO:
            self.errors.append(msg)

    def logerror(self, msg: str) -> str:
        self.log(msg, level=logging.ERROR)

    def logwarning(self, msg: str) -> str:
        self.log(msg, level=logging.WARNING)

    def loginfo(self, msg: str) -> str:
        self.log(msg, level=logging.INFO)

    """Use the following generators to iterate through gongans and beats if you 
    want to use the logging methods of this class. This will ensure that the the 
    logging is prefixed with the correct gongan and beat ids.
    """

    def gongan_iterator(self, object: Any):
        if not hasattr(object, "gongans"):
            raise Exception("base object has no attribute `gongans`")
        for gongan in object.gongans:
            self.curr_gongan_id = gongan.id
            self.curr_beat_id = None
            yield gongan

    def beat_iterator(self, object: Any):
        if not hasattr(object, "beats"):
            raise Exception("base object has no attribute `beats`")
        for beat in object.beats:
            self.curr_beat_id = beat.id
            yield beat

    @property
    def has_errors(self):
        return len(self.errors) > 0
