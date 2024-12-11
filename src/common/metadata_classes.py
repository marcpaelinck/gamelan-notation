import json
import re
from dataclasses import field
from typing import Any, Literal, Optional, Union

import regex
from pydantic import BaseModel, Field, field_validator

from src.common.constants import (
    DEFAULT,
    InstrumentPosition,
    InstrumentType,
    NotationEnum,
)


# MetaData related constants
class DynamicLevel(NotationEnum):
    PIANO = "p"
    MEZZOFORTE = "mf"
    FORTE = "f"


class GonganType(NotationEnum):
    REGULAR = "regular"
    KEBYAR = "kebyar"
    GINEMAN = "gineman"


class MetaDataSwitch(NotationEnum):
    OFF = "off"
    ON = "on"


class ValidationProperty(NotationEnum):
    BEAT_DURATION = "beat-duration"
    STAVE_LENGTH = "stave-length"
    INSTRUMENT_RANGE = "instrument-range"
    KEMPYUNG = "kempyung"


class Scope(NotationEnum):
    GONGAN = "GONGAN"
    SCORE = "SCORE"


class MetaDataBaseType(BaseModel):
    metatype: Literal[""]
    scope: Optional[Scope] = Scope.GONGAN
    _processingorder_ = 99

    def model_dump_notation(self):
        json = self.model_dump(exclude_defaults=True)
        del json["metatype"]
        return f"{{{self.metatype} {', '.join([f'{key}={val}' for key, val in json.items()])}}}"


class DynamicsMeta(BaseModel):
    metatype: Literal["DYNAMICS"]
    level: DynamicLevel
    first_beat: Optional[int] = 1
    beat_count: Optional[int] = 0
    passes: Optional[list[int]] = field(
        default_factory=lambda: list([DEFAULT])
    )  # On which pass(es) should goto be performed?


class GonganMeta(MetaDataBaseType):
    metatype: Literal["GONGAN"]
    type: GonganType


class GoToMeta(MetaDataBaseType):
    metatype: Literal["GOTO"]
    label: str
    from_beat: Optional[int] | None = None  # Beat number from which to goto. Default is last beat of the gongan.
    passes: Optional[list[int]] = field(default_factory=list)  # On which pass(es) should goto be performed?

    @property
    def beat_seq(self) -> int:
        # Returns the pythonic sequence id (numbered from 0)
        return self.from_beat - 1 if self.from_beat else -1


class KempliMeta(MetaDataBaseType):
    metatype: Literal["KEMPLI"]
    status: MetaDataSwitch
    beats: Optional[list[int]] = field(default_factory=list)
    scope: Optional[Scope] = Scope.GONGAN


class LabelMeta(MetaDataBaseType):
    metatype: Literal["LABEL"]
    name: str
    beat: Optional[int] = 1
    # Make sure that labels are processed before gotos in same gongan.
    _processingorder_ = 1

    @property
    def beat_seq(self) -> int:
        # Returns the pythonic sequence id (numbered from 0)
        return self.beat - 1


class OctavateMeta(MetaDataBaseType):
    metatype: Literal["OCTAVATE"]
    instrument: InstrumentType
    octaves: int
    scope: Optional[Scope] = Scope.GONGAN

    @field_validator("instrument", mode="before")
    @classmethod
    # Converts 'free format' position tags to InstrumentPosition values.
    def normalize_positions(cls, data: str) -> InstrumentPosition:
        # Delay import to avoid circular reference.
        from src.common.lookups import LOOKUP

        return LOOKUP.TAG_TO_POSITION[data][0]


class PartMeta(MetaDataBaseType):
    metatype: Literal["PART"]
    name: str


class RepeatMeta(MetaDataBaseType):
    metatype: Literal["REPEAT"]
    count: int = 1


class SuppressMeta(MetaDataBaseType):
    metatype: Literal["SUPPRESS"]
    positions: list[InstrumentPosition] = field(default_factory=list)
    passes: Optional[list[int]] = field(default_factory=list)
    beats: list[int] = field(default_factory=list)

    @field_validator("positions", mode="before")
    @classmethod
    # Converts 'free format' position tags to InstrumentPosition values.
    def normalize_positions(cls, data: list[str]) -> list[InstrumentPosition]:
        # Delay import to avoid circular reference.
        from src.common.lookups import LOOKUP

        return sum((LOOKUP.TAG_TO_POSITION[pos] for pos in data), [])


class TempoMeta(MetaDataBaseType):
    metatype: Literal["TEMPO"]
    bpm: int
    first_beat: Optional[int] = 1
    beat_count: Optional[int] = 0
    passes: Optional[list[int]] = field(
        default_factory=lambda: list([DEFAULT])
    )  # On which pass(es) should goto be performed?

    @property
    def first_beat_seq(self) -> int:
        # Returns the pythonic sequence id (numbered from 0)
        return self.first_beat - 1


class ValidationMeta(MetaDataBaseType):
    metatype: Literal["VALIDATION"]
    beats: Optional[list[int]] = field(default_factory=list)
    ignore: list[ValidationProperty]
    scope: Optional[Scope] = Scope.GONGAN


class WaitMeta(MetaDataBaseType):
    metatype: Literal["WAIT"]
    seconds: float = None
    after: bool = True


MetaDataType = Union[
    GonganMeta,
    GoToMeta,
    KempliMeta,
    LabelMeta,
    OctavateMeta,
    PartMeta,
    RepeatMeta,
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
