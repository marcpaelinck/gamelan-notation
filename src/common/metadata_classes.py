import json
import re
from dataclasses import field
from enum import StrEnum
from typing import Any, ClassVar, Literal, Optional, Union

import regex
from pydantic import BaseModel, Field, ValidationInfo, field_validator

from src.common.constants import (
    DEFAULT,
    DynamicLevel,
    InstrumentType,
    NotationEnum,
    Position,
)
from src.settings.constants import InstrumentTagFields
from src.settings.settings import get_run_settings


# MetaData related constants
class GonganType(NotationEnum):
    REGULAR = "regular"
    KEBYAR = "kebyar"
    GINEMAN = "gineman"


class MetaDataSwitch(NotationEnum):
    OFF = "off"
    ON = "on"


class ValidationProperty(NotationEnum):
    BEAT_DURATION = "beat-duration"
    MEASURE_LENGTH = "measure-length"
    INSTRUMENT_RANGE = "instrument-range"
    KEMPYUNG = "kempyung"


class Scope(NotationEnum):
    GONGAN = "GONGAN"
    SCORE = "SCORE"


def tag_to_position_dict() -> dict[str, list[Position]]:
    """Creates a dict that maps 'free format' position tags to a list of InstumentPosition values
    Args:  run_settings (RunSettings):
    Returns (dict[str, list[Position]]):
    """
    TAG = InstrumentTagFields.TAG
    POS = InstrumentTagFields.POSITIONS
    locals_ = {"None": None} | Position._member_map_
    format = lambda val: eval("None" if val == "" else val, locals_)
    run_settings = get_run_settings()
    tag_rec_list = [record | {POS: format(record[POS])} for record in run_settings.data.instrument_tags]
    tag_rec_list += [
        {TAG: instr, POS: [pos for pos in Position if pos.instrumenttype == instr]} for instr in InstrumentType
    ]
    tag_rec_list += [{TAG: pos, POS: [pos]} for pos in Position]
    lookup_dict = {record[TAG]: record[POS] for record in tag_rec_list}

    return lookup_dict


TAG_TO_POSITION = tag_to_position_dict()


class MetaDataBaseModel(BaseModel):
    metatype: Literal[""]
    scope: Optional[Scope] = Scope.GONGAN
    line: int = None
    _processingorder_ = 99

    # name of the paramater whose value may appear in the notation without specifying the parameter
    DEFAULTPARAM: ClassVar[str]

    @classmethod
    def string_to_list(cls, value: str, el_type: type):
        """Tries to to parse a string or a list of strings. If el_type is None, returns a list of strings.
        If el_type is given, the function tries to parse the list elements into `el_type` values.
        `el_type` should either be `float` or a subclass of `StrEnum`.
        Args:
            value (str): a json-interpretable string.
            el_type (type): type to which to convert the list elements. Should either be a subtype of StrEnum
                            or a type that can be cast from string by applying el_type(value).
        Returns:
            list[el_type]:
        """
        if isinstance(value, str):
            # Single string representing a list of strings: parse into a list of strings
            # First add double quotes around each list element.
            val = re.sub(r"([A-Za-z_][\w]*)", r'"\1"', value)
            try:
                value = json.loads(val)
            except Exception:
                raise ValueError(
                    f"{value} is not a valid list. Elements should be comma separated and enclosed between square brackets []."
                )
        if isinstance(value, list):
            # List of strings: convert strings to enumtype objects.
            if all(isinstance(el, str) for el in value):
                try:
                    return [el_type[el] if issubclass(el_type, StrEnum) else el_type(el) for el in value]
                except Exception:
                    ValueError(f"Could not convert the elements of {value} to {el_type} types.")
            elif all(isinstance(el, el_type) for el in value):
                # List of el_type: return as-is
                return value
        else:
            raise ValueError(f"Could not convert {value} into a list of {el_type}.")

    def model_dump_notation(self):
        json = self.model_dump(exclude_defaults=True)
        del json["line"]
        del json["metatype"]
        if self.DEFAULTPARAM:
            defval = json[self.DEFAULTPARAM]
            del json[self.DEFAULTPARAM]
        return f"{{{self.metatype} {defval} {' '.join([f'{key}={val}' for key, val in json.items()])}}}".strip()


class GradualChangeMetadata(MetaDataBaseModel):
    # Generic class that represent a value that can gradually
    # change over a number of beats, such as tempo or dynamics.
    value: int = None
    first_beat: Optional[int] = 1
    beat_count: Optional[int] = 0
    passes: Optional[list[int]] = field(
        default_factory=lambda: list([DEFAULT])
    )  # On which pass(es) should goto be performed?

    @property
    def first_beat_seq(self) -> int:
        # Returns the pythonic sequence id (numbered from 0)
        return self.first_beat - 1


# THE METADATA CLASSES

# Reusable validators:


def normalize_positions(cls, data: list[str]) -> list[Position]:
    try:
        return sum((TAG_TO_POSITION[pos] for pos in data), [])
    except:
        raise ValueError(f"Unrecognized instrument position in {data}.")


class DynamicsMeta(GradualChangeMetadata):
    metatype: Literal["DYNAMICS"]
    # Currently, an empty list stands for all positions.
    positions: list[Position] = field(default_factory=list)
    abbreviation: str = ""
    DEFAULTPARAM = "abbreviation"

    # validators
    _normalize_position_list: classmethod = field_validator("positions", mode="before")(normalize_positions)
    # @field_validator("positions", mode="before")
    # @classmethod
    # # Converts 'free format' position tags to Position values.
    # def normalize_positions(cls, data: list[str]) -> list[Position]:
    #     try:
    #         return sum((TAG_TO_POSITION[pos] for pos in data), [])
    #     except:
    #         raise ValueError(f"Unrecognized instrument position in {data}.")

    @field_validator("abbreviation", mode="after")
    @classmethod
    def set_value_after(cls, abbr: int, valinfo: ValidationInfo):
        # Set value to velocity.
        # TODO: This is not very nice code but GradualChangeMetadata expects `value` to be an int.
        # Is there a better way to do this?
        try:
            run_settingss = get_run_settings()
            valinfo.data["value"] = run_settingss.midi.dynamics[abbr]
        except:
            # Should not occur because the validator is called after resolving the other fields
            raise Exception(f"illegal value for dynamics: {abbr}")
        return abbr


class GonganMeta(MetaDataBaseModel):
    metatype: Literal["GONGAN"]
    type: GonganType
    DEFAULTPARAM = "type"


class GoToMeta(MetaDataBaseModel):
    metatype: Literal["GOTO"]
    label: str
    from_beat: Optional[int] = -1  # Beat number from which to goto. Default is last beat of the gongan.
    passes: Optional[list[int]] = [DEFAULT]  # On which pass(es) should goto be performed?
    DEFAULTPARAM = "label"

    @property
    def beat_seq(self) -> int:
        # Returns the pythonic sequence id (numbered from 0)
        return self.from_beat - 1 if self.from_beat > 0 else -1


class KempliMeta(MetaDataBaseModel):
    metatype: Literal["KEMPLI"]
    status: MetaDataSwitch
    beats: Optional[list[int]] = field(default_factory=list)
    scope: Optional[Scope] = Scope.GONGAN
    DEFAULTPARAM = "status"


class AutoKempyungMeta(MetaDataBaseModel):
    metatype: Literal["AUTOKEMPYUNG"]
    status: MetaDataSwitch
    scope: Optional[Scope] = Scope.GONGAN
    DEFAULTPARAM = "status"


class LabelMeta(MetaDataBaseModel):
    metatype: Literal["LABEL"]
    name: str
    beat: Optional[int] = 1
    # Make sure that labels are processed before gotos in same gongan.
    _processingorder_ = 1
    DEFAULTPARAM = "name"

    @property
    def beat_seq(self) -> int:
        # Returns the pythonic sequence id (numbered from 0)
        return self.beat - 1


class OctavateMeta(MetaDataBaseModel):
    metatype: Literal["OCTAVATE"]
    instrument: InstrumentType
    octaves: int
    scope: Optional[Scope] = Scope.GONGAN
    DEFAULTPARAM = "instrument"

    @field_validator("instrument", mode="before")
    @classmethod
    # Converts 'free format' position tags to Position values.
    # TODO the tag might refer to more than one instrument. Consider replacing
    # the single instrument attribute with a list of instruments.
    def normalize_positions(cls, data: str) -> Position:
        return TAG_TO_POSITION[data][0].instrumenttype


class PartMeta(MetaDataBaseModel):
    metatype: Literal["PART"]
    name: str
    DEFAULTPARAM = "name"


class RepeatMeta(MetaDataBaseModel):
    metatype: Literal["REPEAT"]
    count: int = 1
    DEFAULTPARAM = "count"


class SequenceMeta(MetaDataBaseModel):
    metatype: Literal["SEQUENCE"]
    value: list[str] = field(default_factory=list)
    DEFAULTPARAM = "value"


class SuppressMeta(MetaDataBaseModel):
    metatype: Literal["SUPPRESS"]
    positions: list[Position] = field(default_factory=list)
    passes: Optional[list[int]] = field(default_factory=list)
    beats: list[int] = field(default_factory=list)
    DEFAULTPARAM = "positions"

    # validators
    _normalize_position_list: classmethod = field_validator("positions", mode="before")(normalize_positions)

    # @field_validator("positions", mode="before")
    # @classmethod
    # # Converts 'free format' position tags to Position values.
    # def normalize_positions(cls, data: list[str]) -> list[Position]:
    #     try:
    #         return sum((TAG_TO_POSITION[pos] for pos in data), [])
    #     except:
    #         raise ValueError(f"Unrecognized instrument position in {data}.")


class TempoMeta(GradualChangeMetadata):
    metatype: Literal["TEMPO"]
    DEFAULTPARAM = "value"


class ValidationMeta(MetaDataBaseModel):
    metatype: Literal["VALIDATION"]
    beats: Optional[list[int]] = field(default_factory=list)
    ignore: list[ValidationProperty]
    scope: Optional[Scope] = Scope.GONGAN
    DEFAULTPARAM = None


class WaitMeta(MetaDataBaseModel):
    metatype: Literal["WAIT"]
    seconds: float = None
    after: bool = True
    passes: Optional[list[int]] = field(
        default_factory=lambda: list(range(99, -1))
    )  # On which pass(es) should goto be performed? Default is all passes.
    # TODO: devise a more elegant way to express this, e.g. with "ALL" value.
    DEFAULTPARAM = None


MetaDataType = Union[
    DynamicsMeta,
    GonganMeta,
    GoToMeta,
    KempliMeta,
    AutoKempyungMeta,
    LabelMeta,
    OctavateMeta,
    PartMeta,
    RepeatMeta,
    SequenceMeta,
    SuppressMeta,
    TempoMeta,
    ValidationMeta,
    WaitMeta,
]


class MetaData(BaseModel):
    data: MetaDataType = Field(..., discriminator="metatype")

    @classmethod
    def __get_all_subtype_fieldnames__(cls):
        membertypes = list(MetaDataType.__dict__.values())[4]
        return {fieldname for member in membertypes for fieldname in member.model_fields.keys()}

    @classmethod
    def __is_list__(cls, value):
        return value.startswith("[") and value.endswith("]")

    @field_validator("data", mode="before")
    @classmethod
    def convert_to_proper_json(cls, data: str) -> dict[Any]:
        """Converts the metadata syntax used in the notation into regular JSON strings.
            metadata format: {META_KEYWORD keyword1=value1[keywordN=valueN] }
        Args:
            x (_type_): _description_

        Returns:
            _type_: _description_
        """
        if not isinstance(data, str):
            return data

        meta = data.strip()
        membertypes = MetaDataType.__dict__["__args__"]
        # create a dict containing the valid parameters for each metadata keyword.
        # Format: {<meta-keyword>: [<parameter1>, <parameter2>, ...]}
        field_dict = {
            member.model_fields["metatype"].annotation.__args__[0]: [
                param for param in list(member.model_fields.keys()) if param != "metatype"
            ]
            for member in membertypes
        }
        # Try to retrieve the keyword
        keyword_pattern = r"\{ *([A-Z]+) +"
        match = regex.match(keyword_pattern, meta)
        if not match:
            # NOTE All exceptions in this method are unit tested by checking the error number
            # a the beginning of the error message.
            raise Exception(f"Err1 - Bad metadata format {data}: could not determine metadata type.")
        meta_keyword = match.group(1)
        if not meta_keyword in field_dict.keys():
            raise Exception(f"Err2 - Metadata {data} has an invalid keyword {meta_keyword}.")

        # Retrieve the corresponding parameter names
        param_names = field_dict[meta_keyword]

        # Create a match pattern for the parameter values
        value_pattern_list = [
            r"(?P<value>'[^']+')",  # quoted value (single quotes)
            r"(?P<value>\"[^\"]+\")",  # quoted value (double quotes)
            r"(?P<value>\[[^\[\]]+\])",  # list
            r"(?P<value>[^,\"'\[\]]+)",  # simple unquoted value
        ]
        value_pattern = "(?:" + "|".join(value_pattern_list) + ")"

        # Create a pattern to validate the general format of the string, without validating the parameter names.
        # This test is performed separately in order to have a more specific error handling.
        single_param_pattern = r"(?: *(?P<parameter>[\w]+) *= *" + value_pattern + " *)"
        multiple_params_pattern = "(?:" + single_param_pattern + ", *)*" + single_param_pattern
        full_metadata_pattern = r"^\{ *" + meta_keyword + " +" + multiple_params_pattern + r"\}"
        # Validate the general structure.
        match = regex.fullmatch(full_metadata_pattern, meta)
        if not match:
            raise Exception(
                f"Err3 - Bad metadata format {data}, please check the format. Are the parameters separated by commas?"
            )

        # Create a pattern requiring valid parameter nammes exclusively.
        single_param_pattern = f"(?: *(?P<parameter>{'|'.join(param_names)})" + r" *= *" + value_pattern + " *)"
        multiple_params_pattern = "(?:" + single_param_pattern + ", *)*" + single_param_pattern
        full_metadata_pattern = r"^\{ *" + meta_keyword + " +" + multiple_params_pattern + r"\}"
        # Validate the parameter names.
        match = regex.fullmatch(full_metadata_pattern, meta)
        if not match:
            raise Exception(
                f"Err4 - Metadata {data} contains invalid parameter(s). Valid values are: {', '.join(field_dict[meta_keyword])}."
            )

        # Capture the (parametername, value) pairs
        groups = [match.captures(i) for i, reg in enumerate(match.regs) if i > 0 and reg != (-1, -1)]

        # Quote non-numeric values, either quoted or non-quoted
        nonnumeric = r'(?: *\'([^"]+)\')|(?: *"([^"]+)")|(?: *(\w*[A-Za-z_]\w*\b) *)'
        # nonnumeric = r"(?: *(\w*[A-Za-z_ ]+\w*) *) *"
        pv = regex.compile(nonnumeric)

        # create a json string
        parameters = [f'"{p}": {pv.sub(r'"\1\2\3"', v)}' for p, v in zip(*groups)]
        json_str = f'{{"metatype": "{meta_keyword}", {" ,".join(parameters)}}}'

        try:
            json_result = json.loads(json_str)
        except:
            raise Exception(f"Err5 - Bad metadata format {data}. Could not parse the value, please check the format.")

        return json_result
