# pylint: disable=missing-module-docstring
import math
import re
from collections import defaultdict
from dataclasses import dataclass, field
from enum import StrEnum, auto
from typing import Any, ClassVar, Optional, Self, override

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
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
    NotationEnum,
    Octave,
    PassSequence,
    Pitch,
    Position,
    RuleParameter,
    RuleType,
    RuleValue,
    Stroke,
    Velocity,
)
from src.common.metadata_classes import (
    AutoKempyungMeta,
    FrequencyType,
    GonganType,
    GoToMeta,
    MetaData,
    MetaDataSwitch,
    MetaDataType,
    SequenceMeta,
    ValidationProperty,
)
from src.settings.classes import Part, RunSettings
from src.settings.constants import (
    FontFields,
    InstrumentFields,
    PresetsFields,
    RuleFields,
)
from src.settings.font_to_valid_notes import get_note_records
from src.settings.settings import RunSettingsListener
from src.settings.utils import tag_to_position_dict

# pylint: disable=missing-class-docstring


@dataclass(frozen=True)
class Tone:
    # A tone is a combination of a pitch and an octave.
    pitch: Pitch
    octave: int
    transformation: RuleValue | None = None

    _MELODIC_PITCHES: ClassVar[dict[str, int]] = [
        Pitch.DING,
        Pitch.DONG,
        Pitch.DENG,
        Pitch.DEUNG,
        Pitch.DUNG,
        Pitch.DANG,
        Pitch.DAING,
    ]

    @property
    def key(self):
        """Returns a sorting key to order the tones by frequency"""
        return self.pitch.sequence + self.octave * 10

    def is_melodic(self):
        """True if the the tone's pitch is one of DING...DAING"""
        return self.pitch in Tone._MELODIC_PITCHES


@dataclass(frozen=True)
class Rule:
    ruletype: RuleType
    positions: Position
    parameters: dict[RuleParameter, Any]


class Instrument(BaseModel, RunSettingsListener):

    _POS_TO_INSTR: ClassVar[dict[Position, "Instrument"]]
    _RULES: ClassVar[dict[Position, dict[RuleType, list[Rule]]]]
    _MAX_RANGE: list[Tone]

    group: InstrumentGroup
    positions: list[Position]
    instrumenttype: InstrumentType
    position_ranges: dict[Position, list[Tone]] = Field(default_factory=lambda: defaultdict(list))
    extended_position_ranges: dict[Position, list[Tone]] = Field(default_factory=lambda: defaultdict(list))
    instrument_range: list[Tone] = Field(default_factory=list)

    @classmethod
    @override
    def cls_initialize(cls, run_settings: RunSettings):
        cls._init_pos_to_instr(run_settings)
        cls._init_rules(run_settings)

    @classmethod
    def get_instrument(cls, position: Position) -> "Instrument":
        return cls._POS_TO_INSTR[position]

    @classmethod
    def get_range(cls, position: Position, extended: bool = False) -> list[Tone]:
        return (
            cls._POS_TO_INSTR[position].extended_position_ranges[position]
            if extended
            else cls._POS_TO_INSTR[position].position_ranges[position]
        )

    @classmethod
    def get_tones_within_range(
        cls, tone: Tone, position: Position, extended_range: bool = False, match_octave=False
    ) -> list[Tone]:
        # The list is sorted by absolute distance to tone.octave in sequence 0, +1, -1, +2, -2
        return sorted(
            [
                t
                for t in Instrument.get_range(position, extended=extended_range)
                if t.pitch == tone.pitch and (t.octave == tone.octave or not match_octave)
            ],
            key=lambda x: abs(x.octave - tone.octave - 0.1),
        )

    @classmethod
    def interval(cls, tone1: Tone, tone2: Tone) -> int:
        """Returns the difference between the indices of the tones in their natural sorting order.

        Args:
            tone1 (Tone): _description_
            tone2 (Tone): _description_

        Raises:
            Exception: if either tone is not within the instrument group's range.

        Returns:
            int: the interval
        """
        if not (tone1 in cls._MAX_RANGE and tone2 in cls._MAX_RANGE):
            raise ValueError(f"{tone1} and/or {tone2} not within the orchestra's range.")
        return cls._MAX_RANGE.index(tone2) - cls._MAX_RANGE.index(tone1)

    @classmethod
    def get_kempyung_pitch(cls, position, pitch: Pitch, inverse: bool = False) -> Pitch | None:
        return next(
            (
                (p if inverse else k)
                for p, k in cls._RULES[position][RuleType.KEMPYUNG][0].parameters[RuleParameter.NOTE_PAIRS]
                if (k if inverse else p) is pitch
            ),
            None,
        )

    @classmethod
    def get_kempyung_tones_within_range(
        cls, tone: Tone, position, extended_range: bool = False, exact_octave_match: bool = True, inverse: bool = False
    ) -> list[Tone]:
        """Returns all the tones with the kempyung pitch of the given tone and which lie in
        the position's range.

        Args:
            tone (Tone): reference tone.
            position (_type_): position which determines the range.
            extended_range (bool, optional): if True, the extended range should be used, otherwise the 'regular' range. Defaults to False.
            exact_octave_match (bool, optional): If True, returns only the tone that lies within an octave above the reference note. Defaults to True.
            inverse (bool, optional): Return the inverse kempyung (the tone for which the given tone is a kempyung tone)

        Returns:
            list[Tone]: a list of kempyung tones or an empty list if none found.
        """
        kempyung_pitch = cls.get_kempyung_pitch(position, tone.pitch, inverse)
        # List possible octaves, looking at octaves equal or highter than the reference tone first
        try_octaves = [tone.octave, tone.octave + 1, tone.octave + 2, tone.octave - 1, tone.octave - 2]
        oct_interval = Instrument.interval(Tone(Pitch.DONG, 0), Tone(Pitch.DONG, 1))
        inv = -1 if inverse else 1
        k_list = [
            Tone(kempyung_pitch, octave)
            for octave in try_octaves
            if Tone(kempyung_pitch, octave) in Instrument.get_range(position, extended_range)
            and (
                not exact_octave_match
                or 0 < inv * Instrument.interval(tone, Tone(kempyung_pitch, octave)) < oct_interval
            )
        ]
        # Put kempyung tones that are higher than the reference tone first.
        return sorted(
            k_list, key=lambda x: [0, 1, 2, -1, -2].index(math.floor(Instrument.interval(tone, x) / oct_interval))
        )

    def merge(self, other: "Instrument") -> "Instrument":
        if not other:
            return self
        # Merge the data of two Instrument objects.
        self.positions += other.positions  # pylint: disable=no-member; -> incorrect warning
        self.position_ranges = self.position_ranges | other.position_ranges
        self.extended_position_ranges = self.extended_position_ranges | other.extended_position_ranges
        self.instrument_range = sorted(list(set(self.instrument_range + other.instrument_range)), key=lambda x: x.key)
        return self

    @classmethod
    def get_shared_notation_rule(cls, position: Position, unisono_positions: set[Position]) -> Rule:
        rules = cls._RULES.get(position, {}).get(
            RuleType.UNISONO, None
        )  # or cls._RULES.get(RuleValue.ANY, {}).get(RuleType.SHARED_NOTATION, None)
        if rules:
            rule = next(
                (rule for rule in rules if set(rule.parameters[RuleParameter.SHARED_BY]) == set(unisono_positions)),
                None,
            ) or next((rule for rule in rules if rule.parameters[RuleParameter.SHARED_BY] == RuleValue.ANY), None)
            if rule:
                return rule.parameters[RuleParameter.TRANSFORM]
        return None

    @classmethod
    def cast_to_position(
        cls, tone: Tone, position: Position, all_positions: set[Position], metadata: list[MetaData]
    ) -> Tone | None:
        """Returns the equivalent tone for `position`, given that the same notation is common for `all_positions`.
        This method uses instrument rules that describe how to interpret a common notation line for multiple
        positions.

        Args:
            tone (Tone): original 'unisono' tone parsed from the notation.
            position (Position): position for which the rule should apply.
            all_positions (set[Position]): positions that share the same notation.

        Raises:
            Exception: no unisono rule found for the position.

        Returns:
            Tone | None: the tone, cast to the position.
        """
        # Select metadata that affects the rules
        autokempyung = True
        for meta in metadata:
            if (
                isinstance(meta.data, AutoKempyungMeta)
                and meta.data.status == MetaDataSwitch.OFF
                and (not meta.data.positions or position in meta.data.positions)
            ):
                autokempyung = False

        # Rules only apply to melodic pitches.
        if not tone.is_melodic():
            return tone

        rule = Instrument.get_shared_notation_rule(position, set(all_positions))
        if not rule:
            raise ValueError(f"No unisono rule found for {position}.")

        for action in rule:
            match action:
                case RuleValue.SAME_TONE:
                    # retain pitch and octave
                    tones = cls.get_tones_within_range(tone, position, extended_range=False, match_octave=True)
                case RuleValue.SAME_PITCH:
                    # retain pitch, select octave within instrument's range
                    tones = cls.get_tones_within_range(tone, position, extended_range=False, match_octave=False)
                case RuleValue.SAME_PITCH_EXTENDED_RANGE:
                    # retain pitch, select octave within instrument's extended range
                    tones = cls.get_tones_within_range(tone, position, extended_range=True, match_octave=False)
                case RuleValue.EXACT_KEMPYUNG:
                    if autokempyung:
                        # select kempyung tone that lies immediately above the given tone
                        tones = cls.get_kempyung_tones_within_range(
                            tone, position, extended_range=False, exact_octave_match=True
                        )
                    else:
                        tones = cls.get_tones_within_range(
                            tone, position, extended_range=False, match_octave=True
                        ) or cls.get_tones_within_range(tone, position, extended_range=False, match_octave=False)
                case RuleValue.KEMPYUNG:
                    if autokempyung:
                        # select kempyung pitch that lies within instrument's range
                        tones = cls.get_kempyung_tones_within_range(
                            tone, position, extended_range=False, exact_octave_match=False
                        )
                    else:
                        tones = cls.get_tones_within_range(
                            tone, position, extended_range=False, match_octave=True
                        ) or cls.get_tones_within_range(tone, position, extended_range=False, match_octave=False)
            if tones:
                return Tone(pitch=tones[0].pitch, octave=tones[0].octave, transformation=action)

        return None

    @classmethod
    def _parse_range(cls, note_range: str) -> list[Tone]:
        return sorted(
            [Tone(*t) for t in note_range],
            key=lambda x: x.key,
        )

    @staticmethod
    def _get_member_map(classes: list[NotationEnum]) -> dict[str, NotationEnum]:
        """Creates a mapping {value -> object} for the members of all NotationEnum subclasses.
        Args:
            classes (list[NotationEnum]): List of enum classes
        Returns:
            _type_: _description_
        """
        return {m.name: m for cls in classes for m in cls}

    @classmethod
    def _init_pos_to_instr(cls, run_settings: RunSettings):
        """Creates the _POS_TO_INSTR lookup dict."""
        # Field definition
        # pylint: disable=invalid-name
        POSITIONS = InstrumentFields.POSITION + "s"
        POSITION_RANGES = InstrumentFields.POSITION_RANGE + "s"
        EXTENDED_POSITION_RANGES = InstrumentFields.EXTENDED_POSITION_RANGE + "s"
        INSTRUMENT_RANGE = "INSTRUMENT_RANGE"
        # pylint: enable=invalid-name

        # First create a dict with all instruments to merge multiple data records for the same instrument type.
        instr_dict: dict[InstrumentType, Instrument] = defaultdict(lambda: None)
        all_tones = set()

        for row in run_settings.data.instruments:
            if (InstrumentGroup[row["group"]]) != run_settings.instrumentgroup:
                continue
            # Create an Instrument object for the current data record, which contains data for a single
            # instrument position.
            record = row.copy()
            record[POSITIONS] = [position := record[InstrumentFields.POSITION]]
            record[POSITION_RANGES] = {position: [Tone(*tpl) for tpl in record[InstrumentFields.POSITION_RANGE]]}
            record[EXTENDED_POSITION_RANGES] = {
                position: [Tone(*tpl) for tpl in record[InstrumentFields.EXTENDED_POSITION_RANGE]]
                or record[POSITION_RANGES][position]
            }
            record[INSTRUMENT_RANGE] = record[EXTENDED_POSITION_RANGES][position]

            all_tones.update(set(record[INSTRUMENT_RANGE]))
            instrument = Instrument.model_validate(record)
            instr_dict[instrument.instrumenttype] = instrument.merge(instr_dict[instrument.instrumenttype])

        # Invert the dict
        cls._POS_TO_INSTR = {pos: instr for instr in instr_dict.values() for pos in instr.positions}
        cls._MAX_RANGE = sorted(list(all_tones), key=lambda x: x.key)

    @classmethod
    def _init_rules(cls, run_settings: RunSettings):
        """Creates the _RULES_DICT."""
        cls._RULES = defaultdict(lambda: defaultdict(list))
        for row in run_settings.data.rules:
            if (InstrumentGroup[row["group"]]) != run_settings.instrumentgroup:
                continue
            # Create an Instrument object for the current data record, which contains data for a single
            # instrument position.
            record = row.copy()
            for position in (
                Position
                # [pos for pos in Position if not cls._RULES[pos]]
                if record["positions"] == RuleValue.ANY
                else record["positions"]
            ):
                # Replace a generic rule (= valid for any position) with a specific one.
                rulelist: list[Rule] = cls._RULES[position][record[RuleFields.RULETYPE]]
                ruletype = record[RuleFields.RULETYPE]
                generic_rule = next(
                    (r for r in rulelist if r.ruletype == ruletype and r.positions == RuleValue.ANY),
                    None,
                )
                if generic_rule:
                    rulelist.remove(generic_rule)
                rulelist.append(
                    Rule(
                        ruletype=record[RuleFields.RULETYPE],
                        positions=record[RuleFields.POSITIONS],
                        parameters={
                            record[parm]: record[val]
                            for parm, val in [
                                (RuleFields.PARAMETER1, RuleFields.VALUE1),
                                (RuleFields.PARAMETER2, RuleFields.VALUE2),
                            ]
                            if record[parm]
                        },
                    )
                )


class Note(BaseModel, RunSettingsListener):
    # config revalidate_instances forces validation when using model_copy
    model_config = ConfigDict(extra="ignore", frozen=True, revalidate_instances="always")

    # POS_P_O_S_D_R stands for Position, Pitch, Octave, Stroke, Duration, Rest After
    # This uniquely defines a Note object that is mapped to a single MIDI note.
    _VALID_POS_P_O_S_D_R: ClassVar[list[tuple[Position, Pitch, Octave, Stroke, Duration, Duration]]]
    VALIDNOTES: ClassVar[list["Note"]]
    _SYMBOL_TO_NOTE: ClassVar[dict[(Position, str), "Note"]]
    # The following attributes uniquely define a note in VALIDNOTES
    _POS_P_O_S_D_R: ClassVar[tuple[str]] = ("position", "pitch", "octave", "stroke", "duration", "rest_after")
    # The following attributes may never be updated
    _FORBIDDEN_UPDATE_ATTRIBUTES: ClassVar[tuple[str]] = ("midinote", "rootnote", "sample")
    _ANY_DURATION_STROKES: ClassVar[tuple[Stroke]] = (Stroke.EXTENSION, Stroke.TREMOLO, Stroke.TREMOLO_ACCELERATING)
    _ANY_SILENCEAFTER_STROKES: ClassVar[tuple[Stroke]] = (Stroke.SILENCE,)
    _POS_P_O_S_D_R_TO_NOTE: ClassVar[dict[tuple[Position, Pitch, Octave, Stroke, Duration, Duration], "Note"]] = None
    _FONT_SORTING_ORDER: ClassVar[dict[str, int]]

    position: Position
    symbol: str
    pitch: Pitch
    octave: int | None
    stroke: Stroke
    duration: float | None
    rest_after: float | None
    velocity: int | None = None  # If None, will be set according to DynamicMeta setting
    modifier: Modifier | None = Modifier.NONE
    midinote: tuple[int, ...] = (127,)  # 0..128, used when generating MIDI output.
    rootnote: str = ""
    sample: str = ""  # file name of the (mp3) sample.
    transformation_rule: Rule | None = None
    transformation: RuleValue | None = None
    autogenerated: bool = False

    @classmethod
    @override
    def cls_initialize(cls, run_settings: RunSettings):
        """Initializes the class's dict constants"""
        font = run_settings.data.font
        mod_list = list(Modifier)
        cls._FONT_SORTING_ORDER = {sym[FontFields.SYMBOL]: mod_list.index(sym[FontFields.MODIFIER]) for sym in font}

        valid_records = get_note_records(run_settings)
        cls._VALID_POS_P_O_S_D_R = [
            tuple([rec[a] for a in ["position", "pitch", "octave", "stroke", "duration", "rest_after"]])
            for rec in valid_records
        ]
        cls.VALIDNOTES = [Note(**record) for record in valid_records]
        cls._SYMBOL_TO_NOTE = {(n.position, cls.sorted_chars(n.symbol)): n for n in cls.VALIDNOTES}
        cls._POS_P_O_S_D_R_TO_NOTE = {
            (n.position, n.pitch, n.octave, n.stroke, n.duration, n.rest_after): n for n in cls.VALIDNOTES
        }

    @property
    def total_duration(self):
        return self.duration + self.rest_after

    def is_melodic(self):
        return self.to_tone().is_melodic()

    @field_validator("octave", mode="before")
    @classmethod
    def process_nonevals(cls, value):
        if isinstance(value, str) and value.upper() == "NONE":
            return None
        return value

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
    def is_valid_combi(
        cls,
        position: Position,
        pitch: Pitch,
        octave: int | None,
        stroke: Stroke,
        duration: float | None,
        rest_after: float | None,
    ) -> Optional["Note"]:
        if stroke in cls._ANY_DURATION_STROKES:
            # accept any duration value
            return any(
                key
                for key in cls._VALID_POS_P_O_S_D_R
                if key[:4] == (position, pitch, octave, stroke) and key[5] == rest_after
            )
        if stroke in cls._ANY_SILENCEAFTER_STROKES:
            # accept any silence value
            return any(
                key for key in cls._VALID_POS_P_O_S_D_R if key[:5] == (position, pitch, octave, stroke, duration)
            )
        return (position, pitch, octave, stroke, duration, rest_after) in cls._VALID_POS_P_O_S_D_R

    @model_validator(mode="after")
    def validate_note(self) -> Self:
        # No validation before lookups dicts have been initialized.
        if self.is_valid_combi(self.position, self.pitch, self.octave, self.stroke, self.duration, self.rest_after):
            return self
        raise ValueError(
            f"Invalid combination {self.pitch} OCT{self.octave} {self.stroke} "
            f"{self.duration} {self.rest_after} for {self.position}"
        )

    def model_copy(self, update=None) -> Optional["Note"]:  # pylint: disable=arguments-differ
        """Overwrites the default model_copy method to allow for validation check.
        BaseModel.model_copy does not validate the input data.
        """
        update = update or {}
        forbidden = set(update.keys()).intersection(set(self._FORBIDDEN_UPDATE_ATTRIBUTES))
        if any(forbidden):
            raise ValueError("Attempt to update one or more protected note value(s): %s" % forbidden)

        note_record = self.model_dump() | update
        search_record = {key: note_record[key] for key in self._POS_P_O_S_D_R}
        if search_record["stroke"] in self._ANY_DURATION_STROKES:
            update |= {"duration": search_record["duration"]}
            search_record["duration"] = 1
        if search_record["stroke"] in self._ANY_SILENCEAFTER_STROKES:
            update |= {"rest_after": search_record["rest_after"]}
            search_record["rest_after"] = 1

        valid_note = self._POS_P_O_S_D_R_TO_NOTE.get(tuple(search_record.values()), None)
        if not valid_note:
            raise ValueError(
                f"Invalid combination {valid_note.pitch} OCT{valid_note.octave} {valid_note.stroke} "
                f"{valid_note.duration} {valid_note.rest_after} for {valid_note.position}"
            )
        return super(Note, valid_note).model_copy(update=update) if valid_note else None

    def model_copy_x(
        self,
        **kwargs,
    ) -> Optional["Note"]:
        """Returns a note with the same attributes as the input note, except for the given parameters.
           Raises an error if the combination of POS_P_O_S_D_R parameters is not valid.
        Returns:
            Optional[Note]: A copy of the note with updated parameters or None if invalid.
        """
        return self.model_copy(update=kwargs)

    @classmethod
    def get_whole_rest_note(cls, position: Position, resttype: Stroke):
        return cls.get_note(
            position=position, pitch=Pitch.NONE, octave=None, stroke=resttype, duration=1, rest_after=0
        ) or cls.get_note(position=position, pitch=Pitch.NONE, octave=None, stroke=resttype, duration=0, rest_after=1)

    @classmethod
    def get_all_p_o_s(cls, position: Position) -> list[tuple[Pitch, Octave, Stroke]]:
        return set((tup[1], tup[2], tup[3]) for tup in cls._POS_P_O_S_D_R_TO_NOTE.keys() if tup[0] == position)

    @classmethod
    def sorted_chars(cls, chars: str) -> str:
        return "".join(sorted(chars, key=lambda c: cls._FONT_SORTING_ORDER.get(c, 99)))

    def to_tone(self) -> Tone:
        return Tone(self.pitch, self.octave)

    def get_kempyung(self, extended_range=False, exact_octave_match=True, inverse: bool = False) -> "Note":
        k_list = Instrument.get_kempyung_tones_within_range(
            Tone(self.pitch, self.octave),
            self.position,
            extended_range,
            exact_octave_match=exact_octave_match,
            inverse=inverse,
        )
        return self.model_copy_x(pitch=k_list[0].pitch, octave=k_list[0].octave) if k_list else None


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
        presets_rec_list = [
            record for record in preset_records if record[PresetsFields.INSTRUMENTGROUP] == instrumentgroup.value
        ]
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


class MidiNote(BaseModel):
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

    @field_validator("octave", mode="before")
    @classmethod
    def process_nonevals(cls, value):
        if isinstance(value, str) and value.upper() == "NONE":
            return None
        return value


#
# Flow
#


@dataclass
class Measure:
    @dataclass
    class Pass:
        seq: int
        line: int | None = None  # input line
        notes: list[Note] = field(default_factory=list)
        ruletype: RuleType | None = None

    position: Position
    all_positions: list[Position]
    passes: dict[PassSequence, Pass] = field(default_factory=dict)

    @classmethod
    def new(cls, position: Position, notes: list[Note], pass_seq: int = DEFAULT, line: int | None = None):
        # Shorthand method to create a Measure object
        return Measure(
            position=position,
            all_positions=[position],
            passes={pass_seq: Measure.Pass(seq=pass_seq, line=line, notes=notes)},
        )


# Note: Beat is intentionally not a Pydantic subclass because
# it points to itself through the `next`, `prev` and `goto` fields,
# which would otherwise cause an "Infinite recursion" error.
@dataclass
class Beat:
    class Change(BaseModel):
        # BaseModel contains a method to translate a list-like string to an actual list.
        class Type(StrEnum):
            TEMPO = auto()
            DYNAMICS = auto()

        # A change in tempo or velocity.
        new_value: int
        steps: int = 0
        incremental: bool = False
        positions: list[Position] = Field(default_factory=list)

    @dataclass
    class GoTo:
        beat: "Beat"
        frequency: FrequencyType
        passes: list[int]

    @dataclass
    class Repeat:
        class RepeatType(StrEnum):
            GONGAN = auto()
            BEAT = auto()

        goto: "Beat"
        iterations: int
        kind: RepeatType = RepeatType.GONGAN
        _countdown: int = 0

        def reset_countdown(self):
            """Resets the countdown counter to its initial value"""
            self._countdown = self.iterations

        def decr_countdown(self) -> None:
            """increments the countdown counter"""
            self._countdown -= 1

        def get_countdown(self) -> int:
            """returns the countdown counter"""
            return self._countdown

    id: int
    gongan_id: int
    bpm_start: dict[PassSequence, BPM]  # tempo at beginning of beat (can vary per pass)
    bpm_end: dict[PassSequence, BPM]  # tempo at end of beat (can vary per pass)
    velocities_start: dict[PassSequence, dict[Position, Velocity]]  # Same for velocity, specified per position
    velocities_end: dict[PassSequence, dict[Position, Velocity]]
    duration: float
    changes: dict[Change.Type, dict[PassSequence, Change]] = field(default_factory=lambda: defaultdict(dict))
    measures: dict[Position, Measure] = field(default_factory=dict)
    prev: "Beat" = field(default=None, repr=False)  # previous beat in the score
    next: "Beat" = field(default=None, repr=False)  # next beat in the score
    # TODO GOTO REMOVE
    goto: dict[PassSequence, "Beat"] = field(
        default_factory=dict
    )  # next beat to be played according to the flow (GOTO metadata)
    goto_: dict[PassSequence, "Beat.GoTo"] = field(
        default_factory=dict
    )  # next beat to be played according to the flow (GOTO metadata)
    has_kempli_beat: bool = True
    repeat: Repeat = None
    validation_ignore: list[ValidationProperty] = field(default_factory=list)
    _pass_: PassSequence = 0  # Counts the number of times the beat is passed during generation of MIDI file.

    @computed_field
    @property
    def full_id(self) -> str:
        return f"{int(self.gongan_id)}-{self.id}"

    @computed_field
    @property
    def gongan_seq(self) -> int:
        # Returns the pythonic sequence id (numbered from 0)
        return self.gongan_id - 1

    def next_beat_in_flow(self, pass_seq=None):
        return self.goto.get(pass_seq or self._pass_, self.goto.get(DEFAULT, self.next))  # TODO GOTO CHANGE

    def get_bpm_start(self):
        # Return tempo at start of beat for the current pass.
        return self.bpm_start.get(self._pass_, self.bpm_start.get(DEFAULT, None))

    def get_velocity_start(self, position):
        # Return velocity at start of beat for the current pass.
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

    def get_pass(self, position: Position, pass_seq: int = DEFAULT):
        # Convenience function for a much-used query.
        # Especially useful for list comprehensions
        if not position in self.measures.keys():
            return None
        else:
            return self.measures[position].passes[pass_seq]

    def get_notes(self, position: Position, pass_seq: int = DEFAULT, none=None):
        # Convenience function for a much-used query.
        # Especially useful for list comprehensions
        if pass_ := self.get_pass(position=position, pass_seq=pass_seq):
            return pass_.notes
        return none

    def reset_pass_counter(self) -> None:
        """(re-)initializes the pass counter"""
        self._pass_ = 0

    def incr_pass_counter(self) -> None:
        """increments the pass counter"""
        self._pass_ += 1

    def get_pass_counter(self) -> int:
        """returns the pass counter"""
        return self._pass_


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
    _pass_: PassSequence = 0  # Counts the number of times the gongan is passed during generation of MIDI file.

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
    sequences: list[tuple[Gongan, SequenceMeta]] = field(default_factory=list)


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
    global_metadata: list[MetaData] = field(default_factory=list)
    global_comments: list[str] = field(default_factory=list)
    midi_notes_dict: dict[tuple[Position, Pitch, Octave, Stroke], MidiNote] = None
    flowinfo: FlowInfo = field(default_factory=FlowInfo)
    midifile_duration: int = None
    part_info: Part = None


if __name__ == "__main__":
    ...
