import json
import re
from collections import defaultdict
from dataclasses import dataclass, field
from enum import StrEnum, auto
from typing import ClassVar, Optional

from pydantic import (
    BaseModel,
    ConfigDict,
    computed_field,
    field_validator,
    model_validator,
)

from src.common.constants import (
    BPM,
    DEFAULT,
    DataRecord,
    Duration,
    InstrumentGroup,
    InstrumentType,
    Modifier,
    NotationDict,
    Octave,
    Pass,
    Pitch,
    Position,
    Stroke,
    Velocity,
)
from src.common.metadata_classes import (
    GonganType,
    GoToMeta,
    MetaData,
    MetaDataType,
    ValidationProperty,
)
from src.settings.classes import RunSettings
from src.settings.constants import FontFields, PresetsFields
from src.settings.font_to_valid_notes import get_font_characters, get_note_records
from src.settings.settings import get_run_settings


@dataclass
class TimedMessage:
    time: int
    type: str
    note: str = "."
    cumtime: int = -1
    duration: int = -1


@dataclass
class TimingData:
    unit_duration: int
    units_per_beat: int
    beats_per_gongan: int


class NotationModel(BaseModel):
    # Class model containing common utilities.

    @classmethod
    def to_list(cls, value, el_type: type):
        # This method tries to to parse a string or a list of strings
        # into a list of `el_type` values.
        # el_type can only be `float` or a subclass of `StrEnum`.
        if isinstance(value, str):
            # Single string representing a list of strings: parse into a list of strings
            # First add double quotes around each list element.
            val = re.sub(r"([A-Za-z_][\w]*)", r'"\1"', value)
            value = json.loads(val)
        if isinstance(value, list):
            # List of strings: convert strings to enumtype objects.
            if all(isinstance(el, str) for el in value):
                try:
                    return [el_type[el] if issubclass(el_type, StrEnum) else float(el) for el in value]
                except:
                    raise ValueError(f"Could not convert value {value} to a list of {el_type}")
            elif all(isinstance(el, el_type) for el in value):
                # List of el_type: do nothing
                return value
        else:
            raise ValueError(f"Could not convert value {value} to a list of {el_type}")


class Note(NotationModel):
    # config revalidate_instances forces validation when using model_copy
    model_config = ConfigDict(extra="ignore", frozen=True, revalidate_instances="always")

    _VALIDNOTES: ClassVar[list["Note"]]
    _SYMBOL_TO_NOTE: ClassVar[dict[str, "Note"]]
    _POS_P_O_S_D_R_TO_NOTE: ClassVar[dict[tuple[Position, Pitch, Octave, Stroke, Duration, Duration], "Note"]]
    _FONT_SORTING_ORDER: ClassVar[dict[str, int]]

    instrumenttype: InstrumentType
    position: Position
    symbol: str
    pitch: Pitch
    octave: int | None
    stroke: Stroke
    duration: float | None
    rest_after: float | None
    velocity: int = 127
    modifier: Modifier | None = Modifier.NONE
    midinote: list[int] = [127]  # 0..128, used when generating MIDI output.
    rootnote: str = ""
    sample: str = ""  # file name of the (mp3) sample.

    @property
    def total_duration(self):
        return self.duration + self.rest_after

    @field_validator("octave", mode="before")
    @classmethod
    def process_nonevals(cls, value):
        if isinstance(value, str) and value.upper() == "NONE":
            return None
        return value

    @classmethod
    @model_validator(mode="after")
    def validate_note(self):
        if (
            self.position,
            self.pitch,
            self.octave,
            self.stroke,
            self.duration,
            self.rest_after,
        ) in self._POS_P_O_S_D_R_TO_NOTE:
            return self
        raise ValueError(
            f"Invalid combination {self.pitch} OCT{self.octave} {self.stroke} "
            f"{self.duration} {self.rest_after} for {self.position}"
        )

    @classmethod
    def get_note(
        cls,
        position: Position,
        pitch: Pitch,
        octave: int | None,
        stroke: Stroke,
        duration: float | None,
        rest_after: float | None,
    ) -> Optional["Note"]:
        note_record = (position, pitch, octave, stroke, duration, rest_after)
        note: Note = cls._POS_P_O_S_D_R_TO_NOTE.get(note_record, None)
        if note:
            return note.model_copy()
        return None

    @classmethod
    def get_whole_rest_note(cls, position: Position, resttype: Stroke):
        return cls.get_note(
            position=position, pitch=Pitch.NONE, octave=None, stroke=resttype, duration=1, rest_after=0
        ) or cls.get_note(position=position, pitch=Pitch.NONE, octave=None, stroke=resttype, duration=0, rest_after=1)

    @classmethod
    def get_all_p_o_s(cls, position: Position) -> list[tuple[Pitch, Octave, Stroke]]:
        return set((tup[1], tup[2], tup[3]) for tup in cls._POS_P_O_S_D_R_TO_NOTE.keys() if tup[0] == position)

    @classmethod
    def note_from_symbol(cls, symbol: str):
        note = cls._SYMBOL_TO_NOTE.get(symbol, None)
        if note:
            return note.model_copy()
        return None

    @classmethod
    def sorted_chars(cls, chars: str) -> str:
        return "".join(sorted(chars, key=lambda c: cls._FONT_SORTING_ORDER.get(c, 99)))

    @classmethod
    def parse_next_note(cls, notation: str, position: Position) -> Optional["Note"]:
        """Parses the first note from the notation.
        Args: notation (str): a notation string
        Returns: tuple[Optional["Note"], str]: The note
        """
        max_length = min(max(*{len(sym) for _, sym in cls._SYMBOL_TO_NOTE.keys()}), len(notation))
        note = None
        for charcount in range(max_length, 0, -1):
            note = cls._SYMBOL_TO_NOTE.get((position, cls.sorted_chars(notation[:charcount])), None)
            if note:
                return note.model_copy()
        return None

    @classmethod
    def _set_up_dicts(cls, run_settings: RunSettings):
        print(f"INITIALIZING NOTE CLASS FOR COMPOSITION {run_settings.notation.title}")
        font = get_font_characters(run_settings)
        mod_list = list(Modifier)
        cls._FONT_SORTING_ORDER = {sym[FontFields.SYMBOL]: mod_list.index(sym[FontFields.MODIFIER]) for sym in font}

        valid_records = get_note_records(run_settings)
        cls._VALIDNOTES = [Note(**record) for record in valid_records]
        cls._SYMBOL_TO_NOTE = {(n.position, cls.sorted_chars(n.symbol)): n for n in cls._VALIDNOTES}
        cls._POS_P_O_S_D_R_TO_NOTE = {
            (n.position, n.pitch, n.octave, n.stroke, n.duration, n.rest_after): n for n in cls._VALIDNOTES
        }

    @classmethod
    def _build_class(cls):
        run_settings = get_run_settings(cls._set_up_dicts)
        cls._set_up_dicts(run_settings)


# INITIALIZE THE Note CLASS WITH LIST OF VALID NOTES AND CORRESPONDING LOOKUPS
##############################################################################
Note._build_class()
##############################################################################


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


class Preset(NotationModel):
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
    def get_preset(cls, position: Position):
        try:
            return cls._POSITION_TO_PRESET[position]
        except:
            raise ValueError("No preset found for {position}.")

    @classmethod
    def get_preset_dict(cls) -> dict[Position, "Preset"]:
        return cls._POSITION_TO_PRESET.copy()

    @classmethod
    def _create_position_to_preset_dict(cls, run_settings: RunSettings):  # -> dict[Position, Preset]
        """Creates a dict to lookup the preset information for a position
        Args: run_settings (RunSettings):
        Returns: dict[Position, Preset]:
        """
        # Select records for the current instrument group
        preset_records: list[str, str] = run_settings.data.presets
        instrumentgroup: InstrumentGroup = run_settings.instruments.instrumentgroup
        presets_rec_list = [
            record for record in preset_records if record[PresetsFields.INSTRUMENTGROUP] == instrumentgroup.value
        ]
        presets_rec_list = convert_pos_to_list(presets_rec_list, PresetsFields.POSITION, PresetsFields.INSTRUMENTTYPE)
        presets_rec_list = explode_list_by_pos(presets_rec_list, PresetsFields.POSITION)
        presets_obj_list = [Preset.model_validate(record) for record in presets_rec_list]
        cls._POSITION_TO_PRESET = {preset.position: preset for preset in presets_obj_list}

    @classmethod
    def _build_class(cls):
        run_settings = get_run_settings(cls._create_position_to_preset_dict)
        cls._create_position_to_preset_dict(run_settings)


# INITIALIZE THE Preset CLASS TO GENERATE THE POSITION_TO_PRESET LOOKUP DICT
##############################################################################
Preset._build_class()
##############################################################################


class InstrumentTag(NotationModel):
    _TAG_TO_POSITION_LIST: ClassVar[dict[str, list[Position]]]

    tag: str
    positions: list[Position]
    infile: str = ""

    @field_validator("positions", mode="before")
    @classmethod
    def validate_pos(cls, value):
        return cls.to_list(value, Position)

    @classmethod
    def _create_tag_to_position_dict(cls, run_settings: RunSettings) -> dict[str, list[Position]]:
        """Creates a dict that maps 'free format' position tags to a list of InstumentPosition values
        Args:  run_settings (RunSettings):
        Returns (dict[str, list[Position]]):
        """
        tag_obj_list = [InstrumentTag.model_validate(record) for record in run_settings.data.instrument_tags]
        tag_obj_list += [
            InstrumentTag(tag=instr, positions=[pos for pos in Position if pos.instrumenttype == instr])
            for instr in InstrumentType
        ]
        tag_obj_list += [InstrumentTag(tag=pos, positions=[pos]) for pos in Position]
        lookup_dict = {t.tag: t.positions for t in tag_obj_list}

        cls._TAG_TO_POSITION_LIST = lookup_dict

    @classmethod
    def get_positions(cls, tag: str) -> list[Position]:
        return cls._TAG_TO_POSITION_LIST.get(tag, None)

    @classmethod
    def _build_class(cls):
        settings = get_run_settings(cls._create_tag_to_position_dict)
        cls._create_tag_to_position_dict(settings)


# INITIALIZE THE InstrumentTag CLASS TO GENERATE THE TAG_TO_POSITION_LIST LOOKUP DICT
#####################################################################################
InstrumentTag._build_class()
#####################################################################################


class MidiNote(NotationModel):
    instrumenttype: InstrumentType
    positions: list[Position]
    pitch: Pitch
    octave: int | None
    stroke: Stroke
    midinote: list[int]  # 0..128, used when generating MIDI output.
    rootnote: str | None
    sample: str  # file name of the (mp3) sample.
    # preset: Preset
    remark: str

    @field_validator("positions", mode="before")
    @classmethod
    def validate_pos(cls, value):
        return cls.to_list(value, Position)

    @field_validator("octave", mode="before")
    @classmethod
    def process_nonevals(cls, value):
        if isinstance(value, str) and value.upper() == "NONE":
            return None
        return value


#
# Flow
#


# Note: Beat is intentionally not a Pydantic subclass because
# it points to itself through the `next`, `prev` and `goto` fields,
# which would otherwise cause an "Infinite recursion" error.
@dataclass
class Beat:

    class Change(NotationModel):
        # NotationModel contains a method to translate a list-like string to an actual list.
        class Type(StrEnum):
            TEMPO = auto()
            DYNAMICS = auto()

        # A change in tempo or velocity.
        new_value: int
        steps: int = 0
        incremental: bool = False
        positions: list[Position] = field(default_factory=list)

    @dataclass
    class Repeat:
        class RepeatType(StrEnum):
            GONGAN = auto()
            BEAT = auto()

        goto: "Beat"
        iterations: int
        kind: RepeatType = RepeatType.GONGAN
        _countdown: int = 0

        def reset(self):
            self._countdown = self.iterations

    id: int
    gongan_id: int
    bpm_start: dict[Pass, BPM]  # tempo at beginning of beat (can vary per pass)
    bpm_end: dict[Pass, BPM]  # tempo at end of beat (can vary per pass)
    velocities_start: dict[Pass, dict[Position, Velocity]]  # Same for velocity, specified per position
    velocities_end: dict[Pass, dict[Position, Velocity]]
    duration: float
    changes: dict[Change.Type, dict[Pass, Change]] = field(default_factory=lambda: defaultdict(dict))
    staves: dict[Position, list[Note]] = field(default_factory=dict)
    # Exceptions contains alternative staves for specific passes.
    exceptions: dict[(Position, Pass), list[Note]] = field(default_factory=dict)
    prev: "Beat" = field(default=None, repr=False)  # previous beat in the score
    next: "Beat" = field(default=None, repr=False)  # next beat in the score
    goto: dict[Pass, "Beat"] = field(
        default_factory=dict
    )  # next beat to be played according to the flow (GOTO metadata)
    has_kempli_beat: bool = True
    repeat: Repeat = None
    validation_ignore: list[ValidationProperty] = field(default_factory=list)
    _pass_: Pass = 0  # Counts the number of times the beat is passed during generation of MIDI file.

    @computed_field
    @property
    def full_id(self) -> str:
        return f"{int(self.gongan_id)}-{self.id}"

    @computed_field
    @property
    def gongan_seq(self) -> int:
        # Returns the pythonic sequence id (numbered from 0)
        return self.gongan_id - 1

    def next_beat_in_flow(self, pass_=None):
        return self.goto.get(pass_ or self._pass_, self.next)

    def get_bpm_start(self):
        return self.bpm_start.get(self._pass_, self.bpm_start.get(DEFAULT, None))

    def get_velocity_start(self, position):
        velocities_start = self.velocities_start.get(self._pass_, self.velocities_start.get(DEFAULT, None))
        # NOTE intentionally causing Exception if position not in velocities_start
        return velocities_start[position]

    def get_changed_value(
        self, current_value: BPM | Velocity, position: Position, changetype: Change.Type
    ) -> BPM | Velocity | None:
        # Generic function, returns either a BPM or a Velocity value for the current beat.
        # Returns None if the value for the current beat is the same as that of the previous beat.
        # In case of a gradual change over several measures, calculates the value for the current beat.
        change_list = self.changes[changetype]
        change = change_list.get(self._pass_, change_list.get(DEFAULT, None))
        if change and changetype is Beat.Change.Type.DYNAMICS and position not in change.positions:
            change = None
        if change and change.new_value != current_value:
            if change.incremental:
                return current_value + int((change.new_value - current_value) / change.steps)
            else:
                return change.new_value
        return None


@dataclass
class Gongan:
    # A set of beats.
    # A Gongan consists of a set of instrument parts.
    # Gongans in the input file are separated from each other by an empty line.
    id: int
    beats: list[Beat] = field(default_factory=list)
    beat_duration: int = 4
    gongantype: GonganType = GonganType.REGULAR
    metadata: list[MetaData] = field(default_factory=list)
    comments: list[str] = field(default_factory=list)
    _pass_: Pass = 0  # Counts the number of times the gongan is passed during generation of MIDI file.

    def get_metadata(self, cls: MetaDataType):
        return next((meta.data for meta in self.metadata if isinstance(meta.data, cls)), None)


@dataclass
class FlowInfo:
    # Keeps track of statements that modify the sequence of
    # gongans or beats in the score. The main purpose of this
    # class is to keep track of gotos that point to labels that
    # have not yet been encountered while processing the score.
    labels: dict[str, Beat] = field(default_factory=dict)
    gotos: dict[str, tuple[Gongan, GoToMeta]] = field(default_factory=lambda: defaultdict(list))


@dataclass
class Notation:
    notation_dict: NotationDict
    settings: "RunSettings"


@dataclass
class Score:

    title: str
    settings: "RunSettings"
    instrument_positions: set[Position] = None
    gongans: list[Gongan] = field(default_factory=list)
    midi_notes_dict: dict[tuple[Position, Pitch, Octave, Stroke], MidiNote] = None
    flowinfo: FlowInfo = field(default_factory=FlowInfo)
    midifile_duration: int = None
