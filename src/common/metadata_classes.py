import json
import re
from dataclasses import field
from typing import Any, Literal, Optional, Union

import pandas as pd
from pydantic import BaseModel, Field, field_validator, model_validator

from src.common.constants import DEFAULT, PASS, InstrumentPosition, NotationEnum


# MetaData related constants
class MetaDataSwitch(NotationEnum):
    OFF = "off"
    ON = "on"


class GonganType(NotationEnum):
    REGULAR = "regular"
    KEBYAR = "kebyar"
    GINEMAN = "gineman"


class ValidationProperty(NotationEnum):
    BEAT_DURATION = "beat-duration"
    STAVE_LENGTH = "stave-length"
    INSTRUMENT_RANGE = "instrument-range"
    KEMPYUNG = "kempyung"


class MetaDataType(BaseModel):
    metatype: Literal[""]
    _processingorder_ = 99


class TempoMeta(MetaDataType):
    metatype: Literal["tempo"]
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


class LabelMeta(MetaDataType):
    metatype: Literal["label"]
    name: str
    beat: Optional[int] = 1
    # Make sure that labels are processed before gotos in same gongan.
    _processingorder_ = 1

    @property
    def beat_seq(self) -> int:
        # Returns the pythonic sequence id (numbered from 0)
        return self.beat - 1


class GoToMeta(MetaDataType):
    metatype: Literal["goto"]
    label: str
    from_beat: Optional[int] | None = None  # Beat number from which to goto. Default is last beat of the gongan.
    passes: Optional[list[int]] = field(default_factory=list)  # On which pass(es) should goto be performed?

    @property
    def beat_seq(self) -> int:
        # Returns the pythonic sequence id (numbered from 0)
        return self.from_beat - 1 if self.from_beat else -1


class RepeatMeta(MetaDataType):
    metatype: Literal["repeat"]
    count: int = 1


class KempliMeta(MetaDataType):
    metatype: Literal["kempli"]
    status: MetaDataSwitch


class GonganMeta(MetaDataType):
    metatype: Literal["gongan"]
    type: GonganType


class SilenceMeta(MetaDataType):
    metatype: Literal["silence"]
    positions: list[InstrumentPosition] = field(default_factory=list)
    passes: Optional[list[int]] = field(default_factory=list)
    beats: list[int] = field(default_factory=list)


class ValidationMeta(MetaDataType):
    metatype: Literal["validation"]
    beats: Optional[list[int]] = field(default_factory=list)
    ignore: list[ValidationProperty]


MetaDataType = Union[
    TempoMeta,
    LabelMeta,
    GoToMeta,
    RepeatMeta,
    KempliMeta,
    GonganMeta,
    ValidationMeta,
    SilenceMeta,
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
        # Switch metadata keyword to lowercase and add 'metatype: ' in front.
        fieldnames = cls.__get_all_subtype_fieldnames__()
        value = data
        match = r"\{(\w+)"
        p = re.compile(match)
        keyword_uc = p.findall(value)[0]
        value = value.replace(keyword_uc, "metatype: " + keyword_uc.lower() + ", ")
        # Replace equal signs with colon.
        value = value.replace("=", ": ")
        # Split value into (fieldname, fieldvalue) pairs.
        # Field value should be either a single string, or a list of strings starting with '[' and ending with ']'.
        match = "(" + "|".join(fieldnames) + r"): *([^\[\]]*?|\[[^\[\]]*?\])[,}]"
        p = re.compile(match)
        field_list = p.findall(value)
        # quote keywords and strings
        # pf matches field values
        match = r"(\b\w+\b)"
        pf = re.compile(match)
        # pv matches unquoted strings and omits strings representing number values.
        # match = r"(\b\w*[A-Za-z_]\w*\b|\\.*\\)"
        match = r"(\w*[A-Za-z_]\w*\b)"
        pv = re.compile(match)
        quoted_fields = [": ".join((f'"{field}"', pv.sub(r'"\1"', value))) for field, value in field_list]
        value = "{" + ", ".join(quoted_fields) + "}"
        # unquote already quoted strings (which are now double quoted)
        value = value.replace('""', "")
        return json.loads(value)
