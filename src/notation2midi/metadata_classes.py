# pylint: disable=missing-class-docstring
from typing import Annotated, ClassVar, Literal, Union, override

from pydantic import BaseModel, Field, TypeAdapter, ValidationInfo, field_validator

from src.common.constants import DEFAULT, InstrumentType, NotationEnum, Position
from src.settings.classes import RunSettings
from src.settings.settings import RunSettingsListener
from src.settings.utils import tag_to_position_dict


# MetaData related constants
class GonganType(NotationEnum):
    REGULAR = "regular"
    KEBYAR = "kebyar"
    GINEMAN = "gineman"


class MetaDataSwitch(NotationEnum):
    OFF = "off"
    ON = "on"


class FrequencyType(NotationEnum):
    ONCE = "once"
    ALWAYS = "always"


class ValidationProperty(NotationEnum):
    BEAT_DURATION = "beat-duration"
    MEASURE_LENGTH = "measure-length"
    INSTRUMENT_RANGE = "instrument-range"
    KEMPYUNG = "kempyung"


class Scope(NotationEnum):
    GONGAN = "GONGAN"
    SCORE = "SCORE"


class MetaDataBaseModel(BaseModel, RunSettingsListener):
    metatype: Literal[""]
    scope: Scope = Scope.GONGAN
    line: int = None
    processingorder: ClassVar[int] = 99

    # name of the paramater whose value may appear in the notation without specifying the parameter
    DEFAULTPARAM: ClassVar[str]
    _TAG_TO_POSITION: dict[str, list[Position]]

    @classmethod
    @override
    def cls_initialize(cls, run_settings: RunSettings):
        """(Re-)initializes the class's _TAG_TO_POSITION lookup dict.
        The method is called when new run settings are loaded."""
        cls._TAG_TO_POSITION = tag_to_position_dict(run_settings)

    def model_dump_notation(self):
        jsonval = self.model_dump(exclude_defaults=True)
        del jsonval["line"]
        del jsonval["metatype"]
        if self.DEFAULTPARAM:
            defval = jsonval[self.DEFAULTPARAM]
            del jsonval[self.DEFAULTPARAM]
        else:
            defval = ""
        return f"{{{self.metatype} {defval} {' '.join([f'{key}={val}' for key, val in jsonval.items()])}}}".strip()


class GradualChangeMetadata(MetaDataBaseModel):
    # Generic class that represent a value that can gradually
    # change over a number of beats, such as tempo or dynamics.
    value: int = None
    first_beat: int = 1
    beat_count: int = 0
    passes: list[int] = Field(default_factory=lambda: list([DEFAULT]))  # On which pass(es) should goto be performed?

    @property
    def first_beat_seq(self) -> int:
        # Returns the pythonic sequence id (numbered from 0)
        return self.first_beat - 1


# THE METADATA CLASSES


class DynamicsMeta(GradualChangeMetadata):
    metatype: Literal["DYNAMICS"] = "DYNAMICS"
    # Currently, an empty list stands for all positions.
    positions: list[Position]  # PositionsFromTag
    abbreviation: str = ""
    DEFAULTPARAM = "abbreviation"
    DYNAMICS: ClassVar[dict[str, int]] = Field(default_factory=dict)

    @field_validator("abbreviation", mode="after")
    @classmethod
    def set_value_after(cls, abbr: int, valinfo: ValidationInfo):
        # Set value to velocity.
        # TODO: This is not very nice code but GradualChangeMetadata expects `value` to be an int.
        # Is there a better way to do this?
        try:
            valinfo.data["value"] = cls.DYNAMICS[abbr]  # pylint: disable=unsubscriptable-object
        except Exception as exc:
            # Should not occur because the validator is called after resolving the other fields
            raise ValueError("illegal value for dynamics: {}".format(abbr) + str(exc)) from exc
        return abbr

    @classmethod
    def cls_initialize(cls, run_settings: RunSettings):
        cls.DYNAMICS = run_settings.midi.dynamics


class GonganMeta(MetaDataBaseModel):
    metatype: Literal["GONGAN"] = "GONGAN"
    type: GonganType
    DEFAULTPARAM = "type"


class GoToMeta(MetaDataBaseModel):
    metatype: Literal["GOTO"] = "GOTO"
    label: str
    from_beat: int = -1  # Beat number from which to goto. Default is last beat of the gongan.
    passes: list[int] = [DEFAULT]  # On which pass(es) should goto be performed?
    frequency: FrequencyType = FrequencyType.ALWAYS
    DEFAULTPARAM = "label"

    @property
    def beat_seq(self) -> int:
        # Returns the pythonic sequence id (numbered from 0)
        return self.from_beat - 1 if self.from_beat > 0 else -1


class KempliMeta(MetaDataBaseModel):
    metatype: Literal["KEMPLI"] = "KEMPLI"
    status: MetaDataSwitch
    beats: list[int] = Field(default_factory=list)
    scope: Scope = Scope.GONGAN
    DEFAULTPARAM = "status"


class AutoKempyungMeta(MetaDataBaseModel):
    metatype: Literal["AUTOKEMPYUNG"] = "AUTOKEMPYUNG"
    status: MetaDataSwitch
    scope: Scope = Scope.GONGAN
    positions: list[Position] = None  # PositionsFromTag
    DEFAULTPARAM = "status"


class LabelMeta(MetaDataBaseModel):
    metatype: Literal["LABEL"] = "LABEL"
    name: str
    beat: int = 1
    # Make sure that labels are processed before gotos in same gongan.
    _processingorder_ = 1
    DEFAULTPARAM = "name"

    @property
    def beat_seq(self) -> int:
        # Returns the pythonic sequence id (numbered from 0)
        return self.beat - 1


class OctavateMeta(MetaDataBaseModel):
    metatype: Literal["OCTAVATE"] = "OCTAVATE"
    instrument: InstrumentType  # InstrumentFromTag
    octaves: int
    scope: Scope = Scope.GONGAN
    DEFAULTPARAM = "instrument"


class PartMeta(MetaDataBaseModel):
    metatype: Literal["PART"] = "PART"
    name: str
    DEFAULTPARAM = "name"


class RepeatMeta(MetaDataBaseModel):
    metatype: Literal["REPEAT"] = "REPEAT"
    count: int = 1
    frequency: FrequencyType = FrequencyType.ALWAYS
    DEFAULTPARAM = "count"


class SequenceMeta(MetaDataBaseModel):
    metatype: Literal["SEQUENCE"] = "SEQUENCE"
    value: list[str] = Field(default_factory=list)
    frequency: FrequencyType = FrequencyType.ALWAYS
    DEFAULTPARAM = "value"


class SuppressMeta(MetaDataBaseModel):
    metatype: Literal["SUPPRESS"] = "SUPPRESS"
    positions: list[Position]  # PositionsFromTag
    passes: list[int] = Field(default_factory=list)
    beats: list[int] = Field(default_factory=list)
    DEFAULTPARAM = "positions"


class TempoMeta(GradualChangeMetadata):
    metatype: Literal["TEMPO"] = "TEMPO"
    DEFAULTPARAM = "value"


class ValidationMeta(MetaDataBaseModel):
    metatype: Literal["VALIDATION"] = "VALIDATION"
    beats: list[int] = Field(default_factory=list)
    ignore: list[ValidationProperty]
    scope: Scope = Scope.GONGAN
    DEFAULTPARAM = None


class WaitMeta(MetaDataBaseModel):
    metatype: Literal["WAIT"] = "WAIT"
    seconds: float = None
    after: bool = True
    passes: list[int] = Field(
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


# The following two statements generate a MetaData object that can be used for typing, and a MetaDataAdapter class
# that will automatically cast a parsed value to the correct ....Meta class. The class selection for casting is based
# on the value of field 'metatype'. Use MetaDataAdapter.validate_python() to parse a dict value or
# MetaDataAdapter.validate_json() to parse a json string value.
# See the tip at the end of this section: https://docs.pydantic.dev/latest/concepts/unions/#nested-discriminated-unions
# See also documentation about TypeAdapter: https://docs.pydantic.dev/latest/api/type_adapter/#TypeAdapter
MetaData = Annotated[
    Union[
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
    ],
    Field(discriminator="metatype"),
]

MetaDataAdapter = TypeAdapter(MetaData)
