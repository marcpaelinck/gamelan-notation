import json
import re
from dataclasses import field
from typing import Any, Literal, Optional, Union

from pydantic import BaseModel, Field, field_validator

from src.common.constants import (
    DEFAULT,
    InstrumentPosition,
    InstrumentType,
    NotationEnum,
)


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


class SilenceMeta(MetaDataBaseType):
    metatype: Literal["SILENCE"]
    duration: int
    after: bool = True


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


MetaDataType = Union[
    TempoMeta,
    LabelMeta,
    GoToMeta,
    RepeatMeta,
    KempliMeta,
    GonganMeta,
    ValidationMeta,
    SuppressMeta,
    OctavateMeta,
    PartMeta,
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
        value = value.replace(keyword_uc, "metatype: " + keyword_uc + ", ")
        # Replace equal signs with colon.
        value = value.replace("=", ": ")
        # Split value into (fieldname, fieldvalue) pairs.
        # Field value should be either a single string:
        #   [^\[\]]*?
        # or a list of strings starting with '[' and ending with ']':
        #   \[[^\[\]]*?\]
        # Field/value pairs should be separated by a comma or (in case of the last pair) a brace:
        #   [,}]
        match = "(" + "|".join(fieldnames) + r"): *([^\[\]]*?|\[[^\[\]]*?\])[,}]"
        p = re.compile(match)
        field_list = p.findall(value)
        # The following code put quotes around the keywords and string values.
        # `match` matches quoted and unquoted strings and omits strings representing number values.
        # The first component "([^"]+)" will be tried first, which prioritizes matching quoted strings.
        # Note that the capturing brackets are placed within the quotes, so the captured values will be unquoted.
        # If no quoted string can be matched, the second component (\w*[A-Za-z_]\w*\b) will capture single, unquoted
        # non-numeric values.
        match = r'"([^"]+)"|(\w*[A-Za-z_ ]\w*\b)'
        pv = re.compile(match)
        # In the substitution, \1\2 stand for the captured quoted and unquoted strings (only one of these placeholders
        # will contain a non-empty value).
        # Because quoted strings are captured without quotes, quoting either of these values yields
        # the required result.
        quoted_fields = [": ".join((f'"{field}"', pv.sub(r'"\1\2"', value))) for field, value in field_list]
        value = "{" + ", ".join(quoted_fields) + "}"
        # unquote already quoted strings (which are now double quoted)
        value = value.replace('""', "")
        return json.loads(value)
