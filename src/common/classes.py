# pylint: disable=missing-module-docstring
import re
from collections import defaultdict
from dataclasses import dataclass, field
from statistics import mode
from typing import ClassVar, Optional, override

from pydantic import BaseModel, Field, computed_field

from src.common.constants import (
    DEFAULT,
    DataRecord,
    InstrumentGroup,
    InstrumentType,
    NotationDict,
    PassSequence,
    Position,
    RuleType,
)
from src.common.notes import GenericNote, Note
from src.notation2midi.metadata_classes import (
    GonganType,
    GoToMeta,
    MetaData,
    MetaDataType,
    MetaType,
    SequenceMeta,
    ValidationProperty,
)
from src.settings.classes import Part, RunSettings
from src.settings.constants import PresetsFields
from src.settings.settings import RunSettingsListener
from src.settings.utils import tag_to_position_dict

# pylint: disable=missing-class-docstring
# Next statement is to avoid pylint bug when assigning Field to attributes in pydantic class definition
# see bugreport https://github.com/pylint-dev/pylint/issues/10087
# pylint: disable=no-member


def convert_pos_to_list(
    record_list: list[DataRecord], position_title: str, instrumenttype_title: str
) -> list[DataRecord]:
    """Converts the position field in each record to a list containing either a single position if the field is not empty
        otherwise the list of positions that correspond with the instrument type field.
    Args: record_list (list[DataRecord]): A list of 'flat' records (from a data file).
          position_title (str): header of the position field.
          instrumenttype_title (str): header of the instrument type field.
    Returns: list[DataRecord]:
    """
    instr_to_poslist = {instr: [pos for pos in Position if pos.instrumenttype is instr] for instr in InstrumentType}
    presets_list = [
        record
        | {
            position_title: (
                [Position[record[position_title]]]
                if record[position_title]
                else instr_to_poslist[record[instrumenttype_title]]
            )
        }
        for record in record_list
    ]
    return presets_list


def explode_list_by_pos(record_list: list[DataRecord], position_title: str) -> list[DataRecord]:
    """Explode' the list by position, i.e. repeat each record for each position in its list of positions.
    Args: position_title (str): header of the position field.
    Returns: list[DataRecord]:
    """  # 'Explode' the list by position, i.e. repeat each record for each position in its list of positions.
    return [record | {position_title: position} for record in record_list for position in record[position_title]]


class Preset(BaseModel, RunSettingsListener):
    # See http://www.synthfont.com/The_Definitions_File.pdf
    # For port, see https://github.com/spessasus/SpessaSynth/wiki/About-Multi-Port

    _POSITION_TO_PRESET: ClassVar[dict[InstrumentType, "Preset"]]

    instrumenttype: InstrumentType
    position: Position
    bank: int  # 0..127, where 127 is reserved for percussion instruments.
    preset: int  # 0..127
    channel: int  # 0..15
    port: int  # 0..255
    preset_name: str

    @classmethod
    @override
    def cls_initialize(cls, run_settings: RunSettings):
        """Creates a dict to lookup the preset information for a given position
        Args: run_settings (RunSettings):
        Returns: dict[Position, Preset]:
        """
        # Select records for the current instrument group
        preset_records: list[str, str] = run_settings.data.presets
        instrumentgroup: InstrumentGroup = run_settings.instrumentgroup
        presets_rec_list = [record for record in preset_records if record[PresetsFields.GROUP] == instrumentgroup.value]
        presets_rec_list = convert_pos_to_list(presets_rec_list, PresetsFields.POSITION, PresetsFields.INSTRUMENTTYPE)
        presets_rec_list = explode_list_by_pos(presets_rec_list, PresetsFields.POSITION)
        presets_obj_list = [Preset.model_validate(record) for record in presets_rec_list]
        cls._POSITION_TO_PRESET = {preset.position: preset for preset in presets_obj_list}

    @classmethod
    def get_preset(cls, position: Position):
        try:
            return cls._POSITION_TO_PRESET[position]
        except Exception as exc:
            raise ValueError("No preset found for {}.".format(position)) from exc

    @classmethod
    def get_preset_dict(cls) -> dict[Position, "Preset"]:
        return cls._POSITION_TO_PRESET.copy()


class InstrumentTag(BaseModel, RunSettingsListener):

    tag: str
    positions: list[Position]
    autocorrect: bool = False  # Indicates that parser should try to octavate to match the position's range.

    _TAG_TO_INSTRUMENTTAG_LIST: ClassVar[dict[str, "InstrumentTag"]]
    _TAG_SEPARATORS: ClassVar[str] = r"/|-|\||,|, "  # expected separators when tags are combined, e.g. ga

    # @field_validator("positions", mode="before")
    # @classmethod
    # def validate_pos(cls, value):  # pylint: disable=missing-function-docstring
    #     return string_to_enum_list(value, Position)

    @classmethod
    @override
    def cls_initialize(cls, run_settings: RunSettings):
        """Creates a dict that maps 'free format' position tags to a record containing the corresponding
        InstumentPosition values
        Args:  run_settings (RunSettings):
        Returns (dict[str, list[Position]]):
        """
        tag_to_pos = tag_to_position_dict(run_settings)
        lookup_dict = {tag: InstrumentTag(tag=tag, positions=value) for tag, value in tag_to_pos.items()}

        cls._TAG_TO_INSTRUMENTTAG_LIST = lookup_dict

    @classmethod
    def get_positions(cls, tag: str) -> list[Position]:
        taglist = re.split(cls._TAG_SEPARATORS, tag)
        try:
            positions_groups = [cls._TAG_TO_INSTRUMENTTAG_LIST.get(t, None).positions for t in taglist]
        except Exception as exc:
            raise ValueError("Incorrect instrument position tag '%s'" % tag) from exc
        return sum(positions_groups, [])


#
# Flow
#


@dataclass
class Measure:
    @dataclass
    class Pass:
        seq: int
        line: int | None = None  # input line
        notesymbols: list[str] = field(default_factory=list)
        genericnotes: list[GenericNote] | None = None
        notes: list[Note] | None = None
        ruletype: RuleType | None = None
        autogenerated: bool = False  # True: pass does not occur in the source but was generated
        # to emulate the flow of the score. This attribute is used by the PDF generator to skip
        # Autogenerated passes.

    position: Position
    all_positions: list[Position]
    passes: dict[PassSequence, Pass] = field(default_factory=dict)

    @classmethod
    def new(
        cls,
        *,
        position: Position,
        notes: list[Note],
        autogenerated,
        pass_seq: int = DEFAULT,
        line: int | None = None,
    ):
        """Shorthand method to create a Measure object"""
        return Measure(
            position=position,
            all_positions=[position],
            passes={pass_seq: Measure.Pass(seq=pass_seq, line=line, notes=notes, autogenerated=autogenerated)},
        )

    @computed_field
    @property
    def duration(self) -> float:
        return sum(note.duration for note in self.passes[DEFAULT].notes)


class Beat(BaseModel):
    id: int
    gongan_id: int
    # duration: float
    measures: dict[Position, Measure] = Field(default_factory=dict)
    prev: Optional["Beat"] = Field(default=None, repr=False)  # previous beat in the score
    next: Optional["Beat"] = Field(default=None, repr=False)  # next beat in the score
    has_kempli_beat: bool = True
    validation_ignore: list[ValidationProperty] = Field(default_factory=list)

    @computed_field
    @property
    def full_id(self) -> str:
        return f"{int(self.gongan_id)}-{self.id}"

    @computed_field
    @property
    def gongan_seq(self) -> int:
        # Returns the pythonic sequence id (numbered from 0)
        return self.gongan_id - 1

    @computed_field
    @property
    def max_duration(self) -> float:
        return max(measure.duration for measure in self.measures.values())

    @computed_field
    @property
    def duration(self) -> float:
        return mode(measure.duration for measure in self.measures.values())

    def get_pass_object(self, position: Position, passid: int = DEFAULT) -> Measure.Pass:
        # Convenience function for a much-used query.
        # Especially useful for list comprehensions
        if not position in self.measures.keys():  # pylint: disable=no-member
            return None
        return self.measures[position].passes.get(
            passid, self.measures[position].passes[DEFAULT] if DEFAULT in self.measures[position].passes else None
        )

    def get_notes(self, position: Position, passid: int = DEFAULT, none=None):
        # Convenience function for a much-used query.
        # Especially useful for list comprehensions
        if pass_ := self.get_pass_object(position=position, passid=passid):
            return pass_.notes
        return none


class Gongan(BaseModel):
    # A set of beats.
    # A Gongan consists of a set of instrument parts.
    # Gongans in the input file are separated from each other by an empty line.
    id: int
    beats: list[Beat] = Field(default_factory=list)
    gongantype: GonganType = GonganType.REGULAR
    metadata: list[MetaData] = Field(default_factory=list)
    comments: list[str] = Field(default_factory=list)
    haslabel: bool = False  # Will be set if the gongan has a Label metadata
    _pass_: PassSequence = 0  # Counts the number of times the gongan is passed during generation of MIDI file.

    def get_metadata(self, cls: MetaDataType):
        return next((meta for meta in self.metadata if isinstance(meta, cls)), None)


@dataclass
class FlowInfo:
    # Keeps track of statements that modify the sequence of
    # gongans or beats in the score. The main purpose of this
    # class is to keep track of gotos that point to labels that
    # have not yet been encountered while processing the score.
    labels: dict[str, Beat] = field(default_factory=dict)
    gotos: dict[str, tuple[Gongan, GoToMeta]] = field(default_factory=lambda: defaultdict(list))
    sequences: list[tuple[Gongan, SequenceMeta]] = field(default_factory=list)


@dataclass
class Score:
    title: str
    settings: RunSettings
    instrument_positions: set[Position] = None
    gongans: list[Gongan] = field(default_factory=list)
    global_metadata: list[MetaData] = field(default_factory=list)
    global_comments: list[str] = field(default_factory=list)
    flowinfo: FlowInfo = field(default_factory=FlowInfo)
    midifile_duration: int = None
    part_info: Part = None

    def metadata(self, metatype: MetaType):
        return [meta for meta in self.global_metadata if meta.metatype is metatype]


@dataclass
class Notation:
    notation_dict: NotationDict
    settings: RunSettings


if __name__ == "__main__":
    ...
