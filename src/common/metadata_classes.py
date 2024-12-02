import json
import re
from dataclasses import field
from typing import Any, ClassVar, Literal, Optional, Union

from pydantic import BaseModel, Field, field_validator, model_validator

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


class Range(NotationEnum):
    GONGAN = "GONGAN"
    SCORE = "SCORE"


class MetaDataSubType(BaseModel):
    metatype: Literal[""]
    range: Optional[Range] = Range.GONGAN
    _processingorder_ = 99


class GonganMeta(MetaDataSubType):
    metatype: Literal["GONGAN"]
    type: GonganType


class GoToMeta(MetaDataSubType):
    metatype: Literal["GOTO"]
    label: str
    from_beat: Optional[int] | None = None  # Beat number from which to goto. Default is last beat of the gongan.
    passes: Optional[list[int]] = field(default_factory=list)  # On which pass(es) should goto be performed?

    @property
    def beat_seq(self) -> int:
        # Returns the pythonic sequence id (numbered from 0)
        return self.from_beat - 1 if self.from_beat else -1


class KempliMeta(MetaDataSubType):
    metatype: Literal["KEMPLI"]
    status: MetaDataSwitch
    beats: list[int] = field(default_factory=list)


class LabelMeta(MetaDataSubType):
    metatype: Literal["LABEL"]
    name: str
    beat: Optional[int] = 1
    # Make sure that labels are processed before gotos in same gongan.
    _processingorder_ = 1

    @property
    def beat_seq(self) -> int:
        # Returns the pythonic sequence id (numbered from 0)
        return self.beat - 1


class OctavateMeta(MetaDataSubType):
    metatype: Literal["OCTAVATE"]
    instrument: InstrumentType
    octaves: int


class PartMeta(MetaDataSubType):
    metatype: Literal["PART"]
    name: str


class RepeatMeta(MetaDataSubType):
    metatype: Literal["REPEAT"]
    count: int = 1


class SilenceMeta(MetaDataSubType):
    # Pointer to cls.common.lookup.TAG_TO_POSITION_LOOKUP
    # TODO temporary solution in order to avoid circular imports. Should look for more elegant solution.
    # There is no guarantee that the attribute will be assigned a value before it is referred to.
    TAG_TO_POSITION_LOOKUP: ClassVar[list] = None

    metatype: Literal["SILENCE"]
    positions: list[InstrumentPosition] = field(default_factory=list)
    passes: Optional[list[int]] = field(default_factory=list)
    beats: list[int] = field(default_factory=list)

    @field_validator("positions", mode="before")
    @classmethod
    # Converts 'free format' position tags to InstrumentPosition values.
    def normalize_positions(cls, data: list[str]) -> list[InstrumentPosition]:
        return sum((cls.TAG_TO_POSITION_LOOKUP[pos] for pos in data), [])


class TempoMeta(MetaDataSubType):
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


class ValidationMeta(MetaDataSubType):
    metatype: Literal["VALIDATION"]
    beats: Optional[list[int]] = field(default_factory=list)
    ignore: list[ValidationProperty]


MetaDataSubType = Union[
    TempoMeta,
    LabelMeta,
    GoToMeta,
    RepeatMeta,
    KempliMeta,
    GonganMeta,
    ValidationMeta,
    SilenceMeta,
    OctavateMeta,
    PartMeta,
]


class MetaData(BaseModel):
    data: MetaDataSubType = Field(..., discriminator="metatype")

    @classmethod
    def __get_all_subtype_fieldnames__(cls):
        membertypes = list(MetaDataSubType.__dict__.values())[4]
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
