from dataclasses import dataclass, fields
from typing import Any, ClassVar, Optional, Self, override
from uuid import UUID, uuid4

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    computed_field,
    field_validator,
    model_validator,
)

from src.common.constants import (
    Duration,
    Modifier,
    Octave,
    Pitch,
    Position,
    RuleParameter,
    RuleType,
    RuleValue,
    Stroke,
)
from src.settings.classes import RunSettings
from src.settings.constants import FontFields
from src.settings.font_to_valid_notes import get_note_records
from src.settings.settings import RunSettingsListener


@dataclass(frozen=True)
class Rule:
    ruletype: RuleType
    positions: Position
    parameters: dict[RuleParameter, Any]


class Tone(BaseModel):
    # A tone is a combination of a pitch and an octave.
    model_config = ConfigDict(extra="ignore", frozen=True)
    pitch: Pitch
    octave: int | None
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

    @computed_field
    @property
    def key(self) -> int:
        """Returns a sorting key to order the tones by frequency"""
        return self.pitch.sequence + self.octave * 10 if self.is_melodic() else 0

    def is_melodic(self):
        """True if the the tone's pitch is one of DING...DAING"""
        return self.pitch in Tone._MELODIC_PITCHES


class UnboundNote(Tone):
    stroke: Stroke
    modifier: Modifier = Modifier.NONE
    duration: float
    rest_after: float
    symbol: str

    @classmethod
    def fieldnames(cls) -> list[str]:
        """Returns the field names"""
        return [f.name for f in fields(cls)]


class BoundNote(UnboundNote):
    position: Position


class MidiNote(BaseModel):
    bound_note: BoundNote
    duration: float
    rest_after: float
    relative_velocity: float = 1.0
    midinote: tuple[int, ...] = (127,)  # 0..128, used when generating MIDI output.


# The class below is a record-like structure that is used to store the intermediate
# results of the notation parser agent. These records will be parsed to the final object model in
# the dict_to_score step. This enables the parsing logic and the object model logic to be
# applied separately, which makes the code easier to understand and to maintain.


class NoteFactory(BaseModel, RunSettingsListener):
    # POS_P_O_S_D_R stands for Position, Pitch, Octave, Stroke, Duration, Rest After
    # This uniquely defines a Note object that is mapped to a single MIDI note.
    _VALID_POS_P_O_S_D_R: ClassVar[list[tuple[Position, Pitch, Octave, Stroke, Duration, Duration]]]
    VALIDNOTES: ClassVar[list["Note"]]
    _SYMBOL_TO_NOTE: ClassVar[dict[(Position, str), "Note"]]
    # The following attributes uniquely define a note in VALIDNOTES
    _POS_P_O_S_D_R: ClassVar[tuple[str]] = ("position", "pitch", "octave", "stroke", "duration", "rest_after")
    # The following attributes may never be updated
    _FORBIDDEN_UPDATE_ATTRIBUTES: ClassVar[tuple[str]] = ("midinote", "rootnote", "sample")
    _FORBIDDEN_COPY_ATTRIBUTES: ClassVar[tuple[str]] = ("uniqueid", "pattern")
    _ANY_DURATION_STROKES: ClassVar[tuple[Stroke]] = (Stroke.EXTENSION, Stroke.TREMOLO, Stroke.TREMOLO_ACCELERATING)
    _ANY_SILENCEAFTER_STROKES: ClassVar[tuple[Stroke]] = (Stroke.SILENCE,)
    _POS_P_O_S_D_R_TO_NOTE: ClassVar[dict[tuple[Position, Pitch, Octave, Stroke, Duration, Duration], "Note"]] = None
    _FONT_SORTING_ORDER: ClassVar[dict[str, int]]

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

    @classmethod
    def get_unbound_note(
        cls,
        position: Position,
        pitch: Pitch,
        octave: int | None,
        stroke: Stroke,
        duration: float | None,
        rest_after: float | None,
    ) -> Optional[UnboundNote]:
        note_record = (position, pitch, octave, stroke, duration, rest_after)
        note: Note = cls._POS_P_O_S_D_R_TO_NOTE.get(note_record, None)
        if note:
            return note.model_copy()
        return None

    @classmethod
    def get_bound_note(
        cls,
        position: Position,
        pitch: Pitch,
        octave: int | None,
        stroke: Stroke,
        duration: float | None,
        rest_after: float | None,
    ) -> Optional[BoundNote]:
        note_record = (position, pitch, octave, stroke, duration, rest_after)
        note: Note = cls._POS_P_O_S_D_R_TO_NOTE.get(note_record, None)
        if note:
            return note.model_copy()
        return None

    @classmethod
    def _is_valid_combi(
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

    # def model_copy(self, update=None) -> Optional["Note"]:  # pylint: disable=arguments-differ
    #     """Overwrites the default model_copy method to allow for validation check.
    #     BaseModel.model_copy does not validate the input data.
    #     """
    #     update = update or {}
    #     forbidden = set(update.keys()).intersection(set(self._FORBIDDEN_UPDATE_ATTRIBUTES))
    #     if any(forbidden):
    #         raise ValueError("Attempt to update one or more protected note value(s): %s" % forbidden)

    #     note_record = self.model_dump(exclude=self._FORBIDDEN_COPY_ATTRIBUTES) | update
    #     search_record = {key: note_record[key] for key in self._POS_P_O_S_D_R}
    #     if search_record["stroke"] in self._ANY_DURATION_STROKES:
    #         update |= {"duration": search_record["duration"]}
    #         search_record["duration"] = 1
    #     if search_record["stroke"] in self._ANY_SILENCEAFTER_STROKES:
    #         update |= {"rest_after": search_record["rest_after"]}
    #         search_record["rest_after"] = 1
    #     update |= {"uniqueid": uuid4()}

    #     valid_note = self._POS_P_O_S_D_R_TO_NOTE.get(tuple(search_record.values()), None)
    #     if not valid_note:
    #         raise ValueError(
    #             (
    #                 "Invalid combination %s OCT%s %s "
    #                 % (search_record["pitch"], search_record["octave"], search_record["stroke"])
    #             )
    #             + (
    #                 "%s %s for %s"
    #                 % ({search_record["duration"]}, {search_record["rest_after"]}, {search_record["position"]})
    #             )
    #         )
    #     updated_args_dict = valid_note.model_dump(exclude=self._FORBIDDEN_COPY_ATTRIBUTES) | update
    #     return Note(**updated_args_dict)

    # def model_copy_x(
    #     self,
    #     **kwargs,
    # ) -> Optional["Note"]:
    #     """Returns a note with the same attributes as the input note, except for the given parameters.
    #        Raises an error if the combination of POS_P_O_S_D_R parameters is not valid.
    #     Returns:
    #         Optional[Note]: A copy of the note with updated parameters or None if invalid.
    #     """
    #     return self.model_copy(update=kwargs)

    @classmethod
    def get_whole_rest_note(cls, position: Position, resttype: Stroke):
        return cls.get_unbound_note(
            position=position, pitch=Pitch.NONE, octave=None, stroke=resttype, duration=1, rest_after=0
        ) or cls.get_unbound_note(
            position=position, pitch=Pitch.NONE, octave=None, stroke=resttype, duration=0, rest_after=1
        )

    @classmethod
    def get_all_p_o_s(cls, position: Position) -> list[tuple[Pitch, Octave, Stroke]]:
        return set((tup[1], tup[2], tup[3]) for tup in cls._POS_P_O_S_D_R_TO_NOTE.keys() if tup[0] == position)

    @classmethod
    def sorted_chars(cls, chars: str) -> str:
        return "".join(sorted(chars, key=lambda c: cls._FONT_SORTING_ORDER.get(c, 99)))


class Note(BaseModel):
    # config revalidate_instances forces validation when using model_copy
    model_config = ConfigDict(extra="ignore", frozen=True, revalidate_instances="always")
    symbol: str | None = None
    velocity: int | None = None  # If None, will be set according to DynamicMeta setting
    modifier: Modifier | None = Modifier.NONE
    # midinote: tuple[int, ...] = (127,)  # 0..128, used when generating MIDI output.
    rootnote: str = ""
    sample: str = ""  # file name of the (mp3) sample.
    autogenerated: bool = False  # True: Note does not occur in the source but was generated
    # to emulate a pattern (e.g. Tremolo). This attribute is used by the PDF generator to skip
    # Autogenerated notes.
    uniqueid: UUID = Field(default_factory=uuid4)
    pattern: list[MidiNote] = Field(default_factory=list)

    @computed_field
    @property
    def pattern_duration(self) -> float:
        return sum([n.duration + n.rest_after for n in self.pattern])
        # return self.duration + self.rest_after

    @field_validator("octave", mode="before")
    @classmethod
    def process_nonevals(cls, value):
        if isinstance(value, str) and value.upper() == "NONE":
            return None
        return value

    # @model_validator(mode="after")
    # def validate_note(self) -> Self:
    #     # No validation before lookups dicts have been initialized.
    #     if NoteFactory._is_valid_combi(
    #         self.position, self.pitch, self.octave, self.stroke, self.duration, self.rest_after
    #     ):
    #         return self
    #     raise ValueError(
    #         f"Invalid combination {self.pitch} OCT{self.octave} {self.stroke} "
    #         f"{self.duration} {self.rest_after} for {self.position}"
    #     )

    # @override
    # def model_post_init(self, context: Any, /) -> None:
    #     if not self.pattern:
    #         self.pattern.append(self.to_pattern_note())  # pylint: disable=no-member
    #     else:
    #         raise ValueError("pattern is not empty")

    def to_pattern_note(self) -> MidiNote:
        return MidiNote(**self.model_dump())  # pylint: disable=too-many-function-args

    def model_copy(self, update=None) -> Optional["Note"]:  # pylint: disable=arguments-differ
        """Overwrites the default model_copy method to allow for validation check.
        BaseModel.model_copy does not validate the input data.
        """
        update = update or {}
        forbidden = set(update.keys()).intersection(set(NoteFactory._FORBIDDEN_UPDATE_ATTRIBUTES))
        if any(forbidden):
            raise ValueError("Attempt to update one or more protected note value(s): %s" % forbidden)

        note_record = self.model_dump(exclude=NoteFactory._FORBIDDEN_COPY_ATTRIBUTES) | update
        search_record = {key: note_record[key] for key in NoteFactory._POS_P_O_S_D_R}
        if search_record["stroke"] in NoteFactory._ANY_DURATION_STROKES:
            update |= {"duration": search_record["duration"]}
            search_record["duration"] = 1
        if search_record["stroke"] in NoteFactory._ANY_SILENCEAFTER_STROKES:
            update |= {"rest_after": search_record["rest_after"]}
            search_record["rest_after"] = 1
        update |= {"uniqueid": uuid4()}

        valid_note = NoteFactory._POS_P_O_S_D_R_TO_NOTE.get(tuple(search_record.values()), None)
        if not valid_note:
            raise ValueError(
                (
                    "Invalid combination %s OCT%s %s "
                    % (search_record["pitch"], search_record["octave"], search_record["stroke"])
                )
                + (
                    "%s %s for %s"
                    % ({search_record["duration"]}, {search_record["rest_after"]}, {search_record["position"]})
                )
            )
        updated_args_dict = valid_note.model_dump(exclude=NoteFactory._FORBIDDEN_COPY_ATTRIBUTES) | update
        return Note(**updated_args_dict)

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

    def to_tone(self) -> Tone:
        return Tone(pitch=self.pitch, octave=self.octave)
