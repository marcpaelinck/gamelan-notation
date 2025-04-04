"""BASE CLASS FOR THE CLASSES THAT PERFORM THE NOTATION -> MIDI CONVERSION"""

import logging
from dataclasses import _MISSING_TYPE, MISSING, dataclass, fields
from enum import StrEnum
from types import UnionType
from typing import Any, Callable, Generator

from src.common.classes import Beat, Gongan, Measure, Score
from src.common.constants import (
    DynamicLevel,
    InstrumentType,
    Modifier,
    Pitch,
    Position,
    Stroke,
)
from src.common.logger import get_logger
from src.common.metadata_classes import (
    FrequencyType,
    GonganType,
    MetaDataSwitch,
    Scope,
    ValidationProperty,
)
from src.settings.classes import RunSettings


class NamedIntID(int):
    """To be used by notation parser, for better readability of the output dict.
    The class formats int values with meaningful names.
    When subclassing this class, change the `name`and optionally the `default` value.
    Each subclass should process its entire input and reports all errors that were encountered.
    The next step in the pipeline should only be performed if no errors were reported in the current step.
    """

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
    """Base class for the classes that each perform a step of the conversion
    from notation to MIDI/PDF/TXT output. It provides a uniform logging format."""

    class ParserType(StrEnum):
        """Used by the logger to determine the source of a warning or error message."""

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
            separator = "-" * int(50 - len(self.parser_type.value) // 2)
            title = f"{separator} {self.parser_type.value} {separator}"
            self.logger.info(title)

            result = func(*args, **kwargs)

            # sep_length = len(title)
            # self.logger.info("=" * sep_length)
            return result

        return wrapper

    def open_logging(self):
        """To be called by the main program before the first parsing step.
        Adds an empty line followed by a title line"""
        title_text = f"NOTATION2MIDI: {self.run_settings.notation.title}"
        separator = "-" * int(50 - len(title_text) // 2)
        title = f"{separator} {title_text} {separator}"
        self.logger.info("")
        self.logger.info(title)

    def close_logging(self):
        """To be called by the main program after the last parsing step.
        Draws a double line (===) followed by an empty line"""
        self.logger.info("=" * 102)
        self.logger.info("")

    def _fmt(self, val: int | None, pos: int):
        """Number formatting, used to format logging messages"""
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
        prefix = (
            f"{extra_spaces}{self._fmt(self.curr_gongan_id,2)}-{self._fmt(self.curr_beat_id,2)} "
            f"|{self._fmt(self.curr_line_nr,4)}| "
        )
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

    def gongan_iterator(self, obj: Score) -> Generator[Gongan, None, None]:
        """Iterates through the gongans of a Score object while setting the curr_gongan_id attribute"""
        if not hasattr(obj, "gongans"):
            raise AttributeError("base object has no attribute `gongans`")
        for gongan in obj.gongans:
            self.curr_gongan_id = gongan.id
            self.curr_beat_id = None
            yield gongan

    def beat_iterator(self, obj: Gongan) -> Generator[Beat, None, None]:
        """Iterates through the beats of a Gongan object while setting the curr_beat_id attribute"""
        if not hasattr(obj, "beats"):
            raise AttributeError("base object has no attribute `beats`")
        for beat in obj.beats:
            self.curr_beat_id = beat.id
            yield beat

    def pass_iterator(self, obj: Measure) -> Generator[Measure.Pass, None, None]:
        """Iterates through the passes of a Measure object while setting the curr_line_nr attribute"""
        if not hasattr(obj, "passes"):
            raise AttributeError("base object has no attribute `passes`")
        for _, pass_seq in obj.passes.items():
            self.curr_line_nr = pass_seq.line
            yield pass_seq

    @property
    def has_errors(self):
        """Determines if any errors were encountered during parsing"""
        return len(self.log_msgs[logging.ERROR]) > 0

    @property
    def has_warnings(self):
        """Determines if any warnings were encountered during parsing"""
        return len(self.log_msgs[logging.WARNING]) > 0


# The classes below are record-like structures that are used to store the intermediate
# results of the notation parser. These records will be parsed to the final object model in
# the dict_to_score step. This enables the parsing logic and the object model logic to be
# applied separately, which makes the code easier to understand and to maintain.

# pylint: disable=missing-class-docstring
# pylint: disable=too-many-instance-attributes


@dataclass(frozen=True, kw_only=False)
class NoteRecord:
    symbol: str
    pitch: Pitch
    octave: int
    stroke: Stroke
    duration: float
    rest_after: float
    modifier: Modifier | None = Modifier.NONE

    @classmethod
    def fieldnames(cls) -> list[str]:
        """Returns the field names"""
        return [f.name for f in fields(cls)]


@dataclass(init=False, kw_only=True)
class MetaDataRecord:
    """This class casts string values to the given types.
    All types used here should be able to cast a string variable, e.g. int("3")
    This holds for all NotationEnum subtypes.
    list[<type>] is also valid.
    Note that casting is not strictly necessary here because MetaDataRecord objects
    will be cast to Pydantic MetaData objects later and Pydantic takes care of casting str values.
    """

    # TODO the list of attributes needs to be kept in sync with
    # the attributes of the metadata classes. Can this be avoided?
    metatype: str
    line: int
    abbreviation: DynamicLevel | _MISSING_TYPE = MISSING
    beat: int | _MISSING_TYPE = MISSING
    beat_count: int | _MISSING_TYPE = MISSING
    beats: list[int] | _MISSING_TYPE = MISSING
    count: int | _MISSING_TYPE = MISSING
    first_beat: int | _MISSING_TYPE = MISSING
    frequency: FrequencyType | _MISSING_TYPE = MISSING
    from_beat: int | _MISSING_TYPE = MISSING
    ignore: list[ValidationProperty] | _MISSING_TYPE = MISSING
    instrument: InstrumentType | _MISSING_TYPE = MISSING
    label: str | _MISSING_TYPE = MISSING
    name: str | _MISSING_TYPE = MISSING
    octaves: int | _MISSING_TYPE = MISSING
    passes: list[int] | _MISSING_TYPE = MISSING
    positions: list[Position] | _MISSING_TYPE = MISSING
    scope: Scope | _MISSING_TYPE = MISSING
    seconds: float | _MISSING_TYPE = MISSING
    status: MetaDataSwitch | _MISSING_TYPE = MISSING
    type: GonganType | _MISSING_TYPE = MISSING
    value: int | list[str] | _MISSING_TYPE = MISSING

    def __init__(self, **kwargs):
        # Ingnore kwargs that are not in the list of fields
        names = self.fieldnames()
        for key, val in kwargs.items():
            if key in names:
                setattr(self, key, self.castany(key, val))

    @classmethod
    def cast(cls, value, fieldtype) -> Any:
        """Casts value or its elements to fieldtype"""
        if hasattr(fieldtype, "__origin__"):
            # see https://docs.python.org/3/library/stdtypes.html#special-attributes-of-genericalias-objects
            if fieldtype.__origin__ is list:
                eltype = fieldtype.__args__[0]
                return [eltype(it) for it in value]
            else:
                # Not implemented GenericAlias origin
                return value
        else:
            return fieldtype(value)

    @classmethod
    def castany(cls, field, value) -> Any:
        """Casts any str or list[str] value to the field's assigned type"""
        typing = cls.__annotations__[field]
        if typing.__class__ is UnionType:
            # Multiple typing options. Try casting to each until success
            for fieldtype in typing.__args__:
                if fieldtype is not _MISSING_TYPE:
                    try:
                        return cls.cast(value, fieldtype)
                    except Exception:  # pylint: disable=broad-exception-caught
                        pass
        else:
            # Single typing.
            try:
                return typing(value)
            except Exception:  # pylint: disable=broad-exception-caught
                pass

        raise ValueError("Incorrect format %s for %s" % (value, field))

    @classmethod
    def fieldnames(cls) -> list[str]:
        """Returns the field names"""
        return [f.name for f in fields(cls)]
