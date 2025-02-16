import json
import math
import re
from collections import defaultdict
from dataclasses import dataclass, field
from enum import StrEnum, auto
from typing import Any, ClassVar, Optional, Self

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
    ParamValue,
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
    FrequencyType,
    GonganType,
    GoToMeta,
    MetaData,
    MetaDataType,
    SequenceMeta,
    ValidationProperty,
)
from src.settings.classes import RunSettings
from src.settings.constants import (
    FontFields,
    InstrumentFields,
    PresetsFields,
    RuleFields,
)
from src.settings.font_to_valid_notes import get_note_records
from src.settings.settings import get_run_settings


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


@dataclass(frozen=True)
class Tone:
    # A tone is a combination of a pitch and an octave.
    pitch: Pitch
    octave: int
    inference_rule: RuleValue | None = None

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
        return self.pitch.index + self.octave * 10

    def is_melodic(self):
        return self.pitch in Tone._MELODIC_PITCHES


class Instrument(NotationModel):
    @dataclass(frozen=True)
    class Rule:
        ruletype: RuleType
        positions: Position
        parameters: dict[RuleParameter, Any]

    _POS_TO_INSTR: ClassVar[dict[Position, "Instrument"]]
    _RULES: ClassVar[dict[Position, dict[RuleType, list[Rule]]]]
    _MAX_RANGE: list[Tone]

    group: InstrumentGroup
    positions: list[Position]
    instrumenttype: InstrumentType
    position_ranges: dict[Position, list[Tone]] = field(default_factory=lambda: defaultdict(list))
    extended_position_ranges: dict[Position, list[Tone]] = field(default_factory=lambda: defaultdict(list))
    instrument_range: list[Tone] = field(default_factory=list)

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
    ) -> Tone | None:
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

    def _merge(self, other: "Instrument") -> "Instrument":
        if not other:
            return self
        # Merge the data of two Instrument objects.
        self.positions += other.positions
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
    def cast_to_position(cls, tone: Tone, position: Position, unisono_positions: set[Position]) -> Tone | None:
        """Returns the equivalent tone for `position`, given that the same notation is common for `unisono_positions`.
        This method uses instrument rules that describe how to interpret a 'unisono' notation line that is
        preceded with a 'multiple instrument' tag such as 'gangsa', 'gangsa p', 'reyong', 'ugal/ga', or 'ug/ga/rey'.

        Args:
            tone (Tone): original 'unisono' tone parsed from the notation.
            position (Position): position for which the rule should apply.
            unisono_positions (set[Position]): positions that share the same notation.

        Raises:
            Exception: no unisono rule found for the position.

        Returns:
            Tone | None: the tone, cast to the position.
        """
        # Rules only apply to melodic pitches.
        if not tone.is_melodic():
            return tone

        rule = Instrument.get_shared_notation_rule(position, set(unisono_positions))
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
                    # select kempyung tone that lies immediately above the given tone
                    tones = cls.get_kempyung_tones_within_range(
                        tone, position, extended_range=False, exact_octave_match=True
                    )
                case RuleValue.KEMPYUNG:
                    # select kempyung pitch that lies within instrument's range
                    tones = cls.get_kempyung_tones_within_range(
                        tone, position, extended_range=False, exact_octave_match=False
                    )
            if tones:
                return Tone(pitch=tones[0].pitch, octave=tones[0].octave, inference_rule=action)

        return None

    @classmethod
    def _parse_range(cls, note_range: str) -> list[Tone]:
        return sorted(
            [Tone(*t) for t in note_range],
            key=lambda x: x.key,
        )

    @classmethod
    def _init_pos_to_instr(cls, run_settings: RunSettings):
        """Creates the _POS_TO_INSTR lookup dict."""
        # Field definition
        POSITIONS = InstrumentFields.POSITION + "s"
        POSITION_RANGES = InstrumentFields.POSITION_RANGE + "s"
        EXTENDED_POSITION_RANGES = InstrumentFields.EXTENDED_POSITION_RANGE + "s"
        INSTRUMENT_RANGE = "INSTRUMENT_RANGE"

        # First create a dict with all instruments to merge multiple data records for the same instrument type.
        instr_dict: dict[InstrumentType, Instrument] = defaultdict(lambda: None)
        all_tones = set()

        for row in run_settings.data.instruments:
            if (InstrumentGroup[row["group"]]) != run_settings.instruments.instrumentgroup:
                continue
            # Create an Instrument object for the current data record, which contains data for a single instrument position.
            locals = (
                InstrumentGroup._member_map_ | InstrumentType._member_map_ | Position._member_map_ | Pitch._member_map_
            )
            record = {key: eval(row[key] or "[]", locals) for key in row.keys()}
            record[POSITIONS] = [position := record[InstrumentFields.POSITION]]
            record[POSITION_RANGES] = {position: cls._parse_range(record[InstrumentFields.POSITION_RANGE])}
            record[EXTENDED_POSITION_RANGES] = {
                position: cls._parse_range(record[InstrumentFields.EXTENDED_POSITION_RANGE])
                or record[POSITION_RANGES][position]
            }
            record[INSTRUMENT_RANGE] = record[EXTENDED_POSITION_RANGES][position]
            all_tones.update(set(record[INSTRUMENT_RANGE]))
            instrument = Instrument.model_validate(record)
            instr_dict[instrument.instrumenttype] = instrument._merge(instr_dict[instrument.instrumenttype])

        # Invert the dict
        cls._POS_TO_INSTR = {pos: instr for instr in instr_dict.values() for pos in instr.positions}
        cls._MAX_RANGE = sorted(list(all_tones), key=lambda x: x.key)

    @classmethod
    def _init_rules(cls, run_settings: RunSettings):
        """Creates the _RULES_DICT."""
        cls._RULES = defaultdict(lambda: defaultdict(list))
        for row in run_settings.data.rules:
            if (InstrumentGroup[row["group"]]) != run_settings.instruments.instrumentgroup:
                continue
            # Create an Instrument object for the current data record, which contains data for a single instrument position.
            locals = (
                InstrumentGroup._member_map_
                | Position._member_map_
                | Pitch._member_map_
                | RuleType._member_map_
                | RuleParameter._member_map_
                | RuleValue._member_map_
            )
            record = {key: eval(row[key] or "None", locals) for key in row.keys()}
            for position in (
                Position
                # [pos for pos in Position if not cls._RULES[pos]]
                if record["positions"] == RuleValue.ANY
                else record["positions"]
            ):
                # Replace a generic rule (= valid for any position) with a specific one.
                rulelist: list[cls.Rule] = cls._RULES[position][record[RuleFields.RULETYPE]]
                ruletype = record[RuleFields.RULETYPE]
                generic_rule = next(
                    (r for r in rulelist if r.ruletype == ruletype and r.positions == RuleValue.ANY),
                    None,
                )
                if generic_rule:
                    rulelist.remove(generic_rule)
                rulelist.append(
                    cls.Rule(
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

    @classmethod
    def _initialize(cls, run_settings: RunSettings):
        print(
            f"INITIALIZING INSTRUMENT CLASS FOR COMPOSITION {run_settings.notation.title} - {run_settings.notation.part.name}"
        )
        cls._init_pos_to_instr(run_settings)
        cls._init_rules(run_settings)
        x = 1

    @classmethod
    def _build_class(cls):
        run_settings = get_run_settings(cls._initialize)
        cls._initialize(run_settings)


# # INITIALIZE THE Instrument CLASS WITH LIST OF VALID NOTES AND CORRESPONDING LOOKUPS
# ##############################################################################
Instrument._build_class()
# ##############################################################################


class Note(NotationModel):
    # config revalidate_instances forces validation when using model_copy
    model_config = ConfigDict(extra="ignore", frozen=True, revalidate_instances="always")

    _VALID_POS_P_O_S_D_R: ClassVar[list[tuple[Position, Pitch, Octave, Stroke, Duration, Duration]]]
    _VALIDNOTES: ClassVar[list["Note"]]
    _SYMBOL_TO_NOTE: ClassVar[dict[(Position, str), "Note"]]
    _POS_P_O_S_D_R_TO_NOTE: ClassVar[dict[tuple[Position, Pitch, Octave, Stroke, Duration, Duration], "Note"]] = None
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
    midinote: tuple[int, ...] = (127,)  # 0..128, used when generating MIDI output.
    rootnote: str = ""
    sample: str = ""  # file name of the (mp3) sample.
    inference_rule: RuleValue | None = None
    autogenerated: bool = False

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

    def model_copy_x(
        self,
        symbol: str | ParamValue = ParamValue.MISSING,
        position: Position | ParamValue = ParamValue.MISSING,
        pitch: Pitch | ParamValue = ParamValue.MISSING,
        octave: int | ParamValue = ParamValue.MISSING,
        stroke: Stroke | ParamValue = ParamValue.MISSING,
        duration: float | ParamValue = ParamValue.MISSING,
        rest_after: float | ParamValue = ParamValue.MISSING,
        inference_rule: RuleValue | ParamValue = ParamValue.MISSING,
    ) -> Optional["Note"]:
        # Returns a note with the same attributes as the input note, except for the given parameters.
        # Uses ParamValue as default value to enable passing None values.
        note_record = (
            position if position is not ParamValue.MISSING else self.position,
            pitch if pitch is not ParamValue.MISSING else self.pitch,
            octave if octave is not ParamValue.MISSING else self.octave,
            stroke if stroke is not ParamValue.MISSING else self.stroke,
            duration if duration is not ParamValue.MISSING else self.duration,
            rest_after if rest_after is not ParamValue.MISSING else self.rest_after,
        )
        note: Note = self._POS_P_O_S_D_R_TO_NOTE.get(note_record, None)
        if note:
            inference_rule = inference_rule if inference_rule is not ParamValue.MISSING else self.inference_rule
            return note.model_copy(update={"symbol": symbol or self.symbol, "inference_rule": inference_rule})
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
    def sorted_chars(cls, chars: str) -> str:
        return "".join(sorted(chars, key=lambda c: cls._FONT_SORTING_ORDER.get(c, 99)))

    def to_tone(self) -> Tone:
        return Tone(self.pitch, self.octave)

    @classmethod
    def parse(
        cls,
        symbol: str,
        position: Position,
        unisono_positions: list[Position],
    ) -> "Note":
        """Parses the given notation symbol to a matching note within the position's range.
        In case multiple positions share the same notation (unisono), this method determines
        the note based on rules (e.g. octavation or kempyung).
        Args:
            symbol (str): notation characters.
            position (Position): position to match.
            unisono_positions (list[Position]): positions that share the same notation.

        Returns:
            Note: _description_
        """
        normalized_symbol = cls.sorted_chars(symbol)

        if len(unisono_positions) == 1:
            # Notation for single position
            if position in unisono_positions:
                return cls._SYMBOL_TO_NOTE[position, normalized_symbol]
            else:
                raise ValueError(f"{position} not in list {unisono_positions}")

        # The notation is for multiple positions. Determine pitch and octave using the 'unisono rules'.

        # Create a Tone object from the the symbol by finding any matching note (disregarding the position)
        reference_note = next((note for note in cls._VALIDNOTES if note.symbol == normalized_symbol), None)
        if not reference_note:
            return None
        reference_tone = reference_note.to_tone()
        tone = Instrument.cast_to_position(reference_tone, position, set(unisono_positions))

        # Return the matching note within the position's range
        return (
            reference_note.model_copy_x(
                position=position, pitch=tone.pitch, octave=tone.octave, inference_rule=tone.inference_rule
            )
            if tone
            else None
        )

    def get_kempyung(self, extended_range=False, exact_octave_match=True, inverse: bool = False) -> "Note":
        k_list = Instrument.get_kempyung_tones_within_range(
            Tone(self.pitch, self.octave),
            self.position,
            extended_range,
            exact_octave_match=exact_octave_match,
            inverse=inverse,
        )
        return self.model_copy_x(pitch=k_list[0].pitch, octave=k_list[0].octave) if k_list else None

    @classmethod
    def _set_up_dicts(cls, run_settings: RunSettings):
        print(
            f"INITIALIZING NOTE CLASS FOR COMPOSITION {run_settings.notation.title} - {run_settings.notation.part.name}"
        )
        font = run_settings.data.font
        mod_list = list(Modifier)
        cls._FONT_SORTING_ORDER = {sym[FontFields.SYMBOL]: mod_list.index(sym[FontFields.MODIFIER]) for sym in font}

        valid_records = get_note_records(run_settings)
        cls._VALID_POS_P_O_S_D_R = [
            tuple([rec[a] for a in ["position", "pitch", "octave", "stroke", "duration", "rest_after"]])
            for rec in valid_records
        ]
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

    tag: str
    positions: list[Position]
    autocorrect: bool = False  # Indicates that parser should try to octavate to match the position's range.

    _TAG_TO_INSTRUMENTTAG_LIST: ClassVar[dict[str, "InstrumentTag"]]

    @field_validator("positions", mode="before")
    @classmethod
    def validate_pos(cls, value):
        return cls.to_list(value, Position)

    @classmethod
    def _create_tag_to_record_dict(cls, run_settings: RunSettings) -> dict[str, list[Position]]:
        """Creates a dict that maps 'free format' position tags to a record containing the corresponding
        InstumentPosition values
        Args:  run_settings (RunSettings):
        Returns (dict[str, list[Position]]):
        """
        tag_obj_list = [InstrumentTag.model_validate(record) for record in run_settings.data.instrument_tags]
        tag_obj_list += [
            InstrumentTag(tag=instr, positions=[pos for pos in Position if pos.instrumenttype == instr])
            for instr in InstrumentType
        ]
        tag_obj_list += [InstrumentTag(tag=pos, positions=[pos]) for pos in Position]
        lookup_dict = {t.tag: t for t in tag_obj_list}

        cls._TAG_TO_INSTRUMENTTAG_LIST = lookup_dict

    @classmethod
    def get_positions(cls, tag: str) -> list[Position]:
        return cls._TAG_TO_INSTRUMENTTAG_LIST.get(tag, None).positions

    @classmethod
    def _build_class(cls):
        settings = get_run_settings(cls._create_tag_to_record_dict)
        cls._create_tag_to_record_dict(settings)


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


@dataclass
class Measure:
    @dataclass
    class Pass:
        seq: int
        line: int | None = None  # input line
        notes: list[Note] = field(default_factory=list)
        ruletype: RuleType | None = None

    position: Position
    passes: dict[PassSequence, Pass] = field(default_factory=dict)

    @classmethod
    def new(cls, position: Position, notes: list[Note], pass_seq: int = DEFAULT, line: int | None = None):
        # Shorthand method to create a Measure object
        return Measure(
            position=position,
            passes={pass_seq: Measure.Pass(seq=pass_seq, line=line, notes=notes)},
        )


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

        def reset(self):
            # Resets the repeat countdown counter
            self._countdown = self.iterations

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
    midi_notes_dict: dict[tuple[Position, Pitch, Octave, Stroke], MidiNote] = None
    flowinfo: FlowInfo = field(default_factory=FlowInfo)
    midifile_duration: int = None
