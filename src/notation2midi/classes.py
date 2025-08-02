"""BASE CLASS FOR THE CLASSES THAT PERFORM THE NOTATION -> MIDI CONVERSION"""

import logging
import sys
from dataclasses import _MISSING_TYPE, MISSING, dataclass, fields
from enum import StrEnum
from types import UnionType
from typing import Any, Generator

from src.common.classes import Beat, Gongan, Measure
from src.common.constants import DynamicLevel, InstrumentType, Position
from src.common.logger import Logging
from src.notation2midi.execution.execution import Score
from src.notation2midi.metadata_classes import (
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


class Agent:
    """Base class for the classes that each perform a step of the conversion
    from notation to MIDI/PDF/TXT output. It provides a uniform logging format.
    IMPORTANT: when subclassing this class, override the _main and _run_condition
               methods and if required also the __init__ method. In the latter case
               call the __init__ method of the Agent main class using super().__init__(...).
    """

    class InputOutputType(StrEnum):
        """Used by the logger to determine the source of a warning or error message."""

        RUNSETTINGS = "run_settings"
        NOTATION = "notation"
        GENERICSCORE = "generic_score"
        BOUNDSCORE = "bound_score"
        PATTERNSCORE = "pattern_score"
        COMPLETESCORE = "complete_score"
        EXECUTION = "execution"
        PART = "part"
        PDFFILE = "pdf_file"

    # Define these constants in each subclass
    LOGGING_MESSAGE: str
    EXPECTED_INPUT_TYPES: tuple[InputOutputType] | None
    RETURN_TYPE: InputOutputType | tuple[InputOutputType] | None

    run_settings = None
    curr_gongan_id: int = None
    curr_measure_id: int = None
    curr_position: Position = None
    curr_line_nr: int = None
    log_msgs: dict[int, str] = {logging.ERROR: [], logging.WARNING: []}
    logger = None
    log_current_pos: bool

    def __init__(self, run_settings: RunSettings):
        self.run_settings = run_settings
        self.logger = Logging.get_logger(self.__class__.__name__)
        self.log_current_pos = True

    # pylint: disable=unused-argument,missing-function-docstring

    # Override this function. It should return True if the _main function
    # should be executed when called.
    @classmethod
    def run_condition_satisfied(cls, run_settings: RunSettings) -> bool: ...

    # Override this function. It should be the main entry point of the agent
    # and should return the agent's output.
    # It should not have any argument except self.
    def _main(self) -> Any: ...

    # pylint: enable=unused-argument,missing-function-docstring

    def run(self) -> Any:
        """Runs the _main method of the subclassed agent."""
        separator = "-" * int(50 - len(self.LOGGING_MESSAGE) // 2)
        title = f"{separator} {self.LOGGING_MESSAGE} {separator}"
        self.logger.info(title)
        result = self._main()  # pylint: disable=assignment-from-no-return
        return result

    def open_logging(self):
        """To be called by the pipeline manager before running the pipeline.
        Adds an empty line followed by a title line"""
        title_text = f"NOTATION2MIDI: {self.run_settings.notationfile.title}"
        separator = "=" * int(50 - len(title_text) // 2)
        title = f"{separator} {title_text} {separator}"
        self.logger.info("")
        self.logger.info(title)

    def close_logging(self):
        """To be called by the pipeline manager after running the pipeline.
        Draws a double line (===) followed by an empty line"""
        self.logger.info("=" * 102)
        self.logger.info("")

    def _fmt(self, val: int | None, pos: int):
        """Number formatting, used to format logging messages"""
        p = f"{pos:02d}"
        return f"{val:{p}d}" if val and self.log_current_pos else " " * pos

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
            f"{extra_spaces}{self._fmt(self.curr_gongan_id,2)}-{self._fmt(self.curr_measure_id,2)} "
            f"|{self._fmt(self.curr_line_nr,4)}| "
        )
        msg = prefix + msg
        self.logger.log(level, msg, *args)
        if level > logging.INFO:
            self.log_msgs[level].append(msg)

    def abort_if_errors(self):
        """Displays a 'program aborted' message and stops execution."""
        if self.has_errors:
            tmp = self.log_current_pos
            self.log_current_pos = False
            self.logerror("Program halted.")
            self.log_current_pos = tmp
            sys.exit()

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
            self.curr_measure_id = None
            yield gongan

    def beat_iterator(self, obj: Gongan) -> Generator[Beat, None, None]:
        """Iterates through the beats of a Gongan object while setting the curr_beat_id attribute"""
        if not hasattr(obj, "beats"):
            raise AttributeError("base object has no attribute `beats`")
        for beat in obj.beats:
            self.curr_measure_id = beat.id
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
        """Determines if any errors were encountered during the agent's process"""
        return len(self.log_msgs[logging.ERROR]) > 0

    @property
    def has_warnings(self):
        """Determines if any warnings were encountered during the agent's process"""
        return len(self.log_msgs[logging.WARNING]) > 0


# pylint: disable=missing-class-docstring
# pylint: disable=too-many-instance-attributes
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
    last_beat: int | _MISSING_TYPE = MISSING
    frequency: FrequencyType | _MISSING_TYPE = MISSING
    from_beat: int | _MISSING_TYPE = MISSING
    ignore: list[ValidationProperty] | _MISSING_TYPE = MISSING
    instrument: InstrumentType | _MISSING_TYPE = MISSING
    label: str | _MISSING_TYPE = MISSING
    name: str | _MISSING_TYPE = MISSING
    octaves: int | _MISSING_TYPE = MISSING
    passes: list[int] | _MISSING_TYPE = MISSING
    iterations: list[int] | _MISSING_TYPE = MISSING
    positions: list[Position] | _MISSING_TYPE = MISSING
    scope: Scope | _MISSING_TYPE = MISSING
    seconds: float | _MISSING_TYPE = MISSING
    status: MetaDataSwitch | _MISSING_TYPE = MISSING
    template: str | _MISSING_TYPE = MISSING
    type: GonganType | _MISSING_TYPE = MISSING
    value: int | list[str] | _MISSING_TYPE = MISSING
    from_value: int | str | None | _MISSING_TYPE = MISSING
    to_value: int | str | _MISSING_TYPE = MISSING
    from_abbr: str | _MISSING_TYPE = MISSING
    to_abbr: str | _MISSING_TYPE = MISSING

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
