# pylint: disable=missing-class-docstring
from typing import Annotated, Any, ClassVar, Literal, Self, Union, override

from pydantic import (
    BaseModel,
    Field,
    TypeAdapter,
    ValidationInfo,
    field_validator,
    model_validator,
)

from src.common.constants import (
    DynamicLevel,
    GonganType,
    InstrumentType,
    NotationEnum,
    Position,
)
from src.settings.classes import RunSettings
from src.settings.settings import RunSettingsListener
from src.settings.utils import tag_to_position_dict


# MetaData related constants
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


class MetaType(NotationEnum):
    AUTOKEMPYUNG = "AUTOKEMPYUNG"
    DYNAMICS = "DYNAMICS"
    GONGAN = "GONGAN"
    GOTO = "GOTO"
    KEMPLI = "KEMPLI"
    LABEL = "LABEL"
    LOOP = "LOOP"
    OCTAVATE = "OCTAVATE"
    PART = "PART"
    SEQUENCE = "SEQUENCE"
    SUPPRESS = "SUPPRESS"
    TEMPO = "TEMPO"
    COPY = "COPY"
    VALIDATION = "VALIDATION"
    WAIT = "WAIT"


class MetaDataBaseModel(BaseModel, RunSettingsListener):
    metatype: MetaType
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
        if self.DEFAULTPARAM:
            defval = jsonval[self.DEFAULTPARAM]
            del jsonval[self.DEFAULTPARAM]
        else:
            defval = ""
        return f"{{{self.metatype} {defval} {' '.join([f'{key}={val}' for key, val in jsonval.items()])}}}".strip()


class GradualChangeMetadata(MetaDataBaseModel):
    # Generic class that represent a value that can gradually
    # change over a number of beats, such as tempo or dynamics.
    # 'virtual' field last_beat can be passed as an alternative for beat_count.
    explicit_gradual_beat: bool = False  # Explicit gradual change format beat1->beat2 in notation.
    explicit_gradual_value: bool = False  # Explicit gradual change format ->value or value1->value2 in notation.
    from_value: int | None = None
    to_value: int
    first_beat: int = 1
    last_beat: int | None = None
    beat_count: int | None = None
    passes: list[int] = Field(default_factory=list)  # On which pass(es) should goto be performed?
    iterations: list[int] = Field(default_factory=list)  # On which iteration(s) should goto be performed?

    @property
    def explicit_gradual(self) -> bool:
        return self.explicit_gradual_beat or self.explicit_gradual_value

    @property
    def first_beat_seq(self) -> int:
        # Returns the pythonic sequence id (numbered from 0)
        return self.first_beat - 1

    @model_validator(mode="after")
    def validate_and_set_beat_count(self) -> Self:
        """Determines the value of beat_count if it is missing.
        Takes into account that last_beat can be passed as an argument instead of beat_count.
        Also takes into account that both beat_count and last_beat are missing: in that
        case, a gradual change over one beat is assumed."""
        if self.explicit_gradual_beat:
            # first_beat and last_beat are given
            if self.last_beat >= self.first_beat:
                self.beat_count = self.last_beat - self.first_beat + 1
            else:
                raise ValueError("Negative beat range for gradual %s change" % self.metatype)

        if self.beat_count is None:
            if self.last_beat is None:
                if self.from_value is None:
                    if self.explicit_gradual:
                        # gradual change over one beat
                        self.beat_count = 1
                    else:
                        # immediate change
                        self.beat_count = 0
                else:
                    # Gradual change with only first_beat value given: assume that the gradual change duration is one beat.
                    self.last_beat = self.first_beat
                    self.beat_count = 1
            else:
                # both first_beat and last_beat have a value. Check for invalid values and set beat_count accordingly.
                if self.beat_count is not None and self.beat_count != self.last_beat - self.first_beat + 1:
                    raise ValueError("%s: 'beat_count' and beat range are contradictory. Remove one." % self.metatype)
                if self.last_beat >= self.first_beat:
                    self.beat_count = self.last_beat - self.first_beat + 1
                else:
                    raise ValueError("Negative range for gradual %s change" % self.metatype)
        if self.beat_count is None:
            raise ValueError("Unexpected error interpreting %s change." % self.metatype)

        return self


# THE METADATA CLASSES


class AutoKempyungMeta(MetaDataBaseModel):
    metatype: Literal[MetaType.AUTOKEMPYUNG] = MetaType.AUTOKEMPYUNG
    status: MetaDataSwitch
    scope: Scope = Scope.GONGAN
    positions: list[Position] = None  # PositionsFromTag
    DEFAULTPARAM = "status"


class DynamicsMeta(GradualChangeMetadata):
    metatype: Literal[MetaType.DYNAMICS] = MetaType.DYNAMICS
    # Currently, an empty list stands for all positions.
    positions: list[Position]  # PositionsFromTag
    from_abbr: str = DynamicLevel
    to_abbr: str = DynamicLevel
    DEFAULTPARAM = "abbreviation"
    DYNAMICS: ClassVar[dict[str, int]] = Field(default_factory=dict)

    @model_validator(mode="before")
    @classmethod
    def set_values(cls, data: Any) -> Any:
        # Set from_value and to_value.
        # TODO: This is not very nice code but GradualChangeMetadata expects `from_value` and `to_value` to be int.
        # Is there a better way to do this?
        if isinstance(data, dict):
            try:
                for abbr_field, value_field in [("from_abbr", "from_value"), ("to_abbr", "to_value")]:
                    if abbr_field in data:
                        # cast dynamics abbreviation to its velocity equivalent.
                        data[value_field] = cls.DYNAMICS[data[abbr_field]]
            except Exception as exc:
                # Should only if cls.DYNAMICS does not contain all possible DynamicLevel values
                raise ValueError("No velocity known for dynamics: %s" % (data[abbr_field]) + str(exc)) from exc
        return data

    @classmethod
    def cls_initialize(cls, run_settings: RunSettings):
        cls.DYNAMICS = run_settings.midi.dynamics


class GonganMeta(MetaDataBaseModel):
    metatype: Literal[MetaType.GONGAN] = MetaType.GONGAN
    type: GonganType
    DEFAULTPARAM = "type"


class GoToMeta(MetaDataBaseModel):
    metatype: Literal[MetaType.GOTO] = MetaType.GOTO
    label: str
    from_beat: int = -1  # Beat number from which to goto. Default is last beat of the gongan.
    passes: list[int] = Field(default_factory=list)  # On which pass(es) should goto be performed?
    cycle: int = 99
    DEFAULTPARAM = "label"

    @property
    def beat_seq(self) -> int:
        # Returns the pythonic sequence id (numbered from 0)
        return self.from_beat - 1 if self.from_beat > 0 else -1


class KempliMeta(MetaDataBaseModel):
    metatype: Literal[MetaType.KEMPLI] = MetaType.KEMPLI
    status: MetaDataSwitch
    beats: list[int] = Field(default_factory=list)
    scope: Scope = Scope.GONGAN
    DEFAULTPARAM = "status"


class LabelMeta(MetaDataBaseModel):
    metatype: Literal[MetaType.LABEL] = MetaType.LABEL
    name: str
    beat: int = 1
    # Make sure that labels are processed before gotos in same gongan.
    _processingorder_ = 1
    DEFAULTPARAM = "name"

    @property
    def beat_seq(self) -> int:
        # Returns the pythonic sequence id (numbered from 0)
        return self.beat - 1


class LoopMeta(MetaDataBaseModel):
    metatype: Literal[MetaType.LOOP] = MetaType.LOOP
    count: int = 1
    frequency: FrequencyType = FrequencyType.ALWAYS  # FrequencyType.ONCE: only first pass
    DEFAULTPARAM = "count"


class OctavateMeta(MetaDataBaseModel):
    metatype: Literal[MetaType.OCTAVATE] = MetaType.OCTAVATE
    instrument: InstrumentType  # InstrumentFromTag
    octaves: int
    scope: Scope = Scope.GONGAN
    DEFAULTPARAM = "instrument"


class PartMeta(MetaDataBaseModel):
    metatype: Literal[MetaType.PART] = MetaType.PART
    name: str
    DEFAULTPARAM = "name"


class SequenceMeta(MetaDataBaseModel):
    metatype: Literal[MetaType.SEQUENCE] = MetaType.SEQUENCE
    value: list[str] = Field(default_factory=list)
    frequency: FrequencyType = FrequencyType.ALWAYS
    DEFAULTPARAM = "value"


class SuppressMeta(MetaDataBaseModel):
    metatype: Literal[MetaType.SUPPRESS] = MetaType.SUPPRESS
    positions: list[Position]  # PositionsFromTag
    passes: list[int] = Field(default_factory=list)
    beats: list[int] = Field(default_factory=list)
    DEFAULTPARAM = "positions"


class TempoMeta(GradualChangeMetadata):
    metatype: Literal[MetaType.TEMPO] = MetaType.TEMPO
    DEFAULTPARAM = "value"


class CopyMeta(MetaDataBaseModel):
    metatype: Literal[MetaType.COPY] = MetaType.COPY
    template: str
    include: list[str] = Field(default_factory=list)
    DEFAULTPARAM = "template"
    _processingorder_ = 10


class ValidationMeta(MetaDataBaseModel):
    metatype: Literal[MetaType.VALIDATION] = MetaType.VALIDATION
    beats: list[int] = Field(default_factory=list)
    ignore: list[ValidationProperty]
    scope: Scope = Scope.GONGAN
    DEFAULTPARAM = None


class WaitMeta(MetaDataBaseModel):
    metatype: Literal[MetaType.WAIT] = MetaType.WAIT
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
    LoopMeta,
    OctavateMeta,
    PartMeta,
    SequenceMeta,
    SuppressMeta,
    TempoMeta,
    CopyMeta,
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
    MetaDataType,
    Field(discriminator="metatype"),
]

MetaDataAdapter = TypeAdapter(MetaData)
