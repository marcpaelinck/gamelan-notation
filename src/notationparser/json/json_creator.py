"""This is the module that actually generates the MIDI messages.
It is used by the MidiGenerator (score_to_midi module).
"""

import json
import re
from functools import reduce
from typing import ClassVar, override

from _ctypes import PyObj_FromPtr
from pydantic import BaseModel, Field, field_serializer

from src.common.classes import Beat
from src.common.constants import Position, SustainType
from src.common.logger import Logging
from src.common.notes import Note, Pattern
from src.settings.classes import RunSettings, RunType

logger = Logging.get_logger(__name__)


class BeatInfo(BaseModel):
    UPDATEFREQ: ClassVar[int] = 24
    fullid: str
    duration: float
    start_bpm: int
    end_bpm: int
    start_velocities: dict[Position, int]
    end_velocities: dict[Position, int]


class NoIndent(object):
    """Value wrapper. See explanation in MyEncoder class def."""

    def __init__(self, value):
        self.value = value


class CompactEncoder(json.JSONEncoder):
    """Disables indentation for parts of a serializable structure that are contained withing a NoIndent object.
    Note: the encoder only seems to work with json.dumps, not with json.dump.
    See https://stackoverflow.com/questions/13249415/how-to-implement-custom-indentation-when-pretty-printing-with-the-json-module
    """

    FORMAT_SPEC = "@@{}@@"
    regex = re.compile(FORMAT_SPEC.format(r"(\d+)"))

    def __init__(self, **kwargs):
        # Save copy of any keyword argument values needed for use here.
        self.__sort_keys = kwargs.get("sort_keys", None)
        super(CompactEncoder, self).__init__(**kwargs)

    @override
    def default(self, o):
        return self.FORMAT_SPEC.format(id(o)) if isinstance(o, NoIndent) else super(CompactEncoder, self).default(o)

    @override
    def encode(self, o):
        format_spec = self.FORMAT_SPEC  # Local var to expedite access.
        json_repr = super(CompactEncoder, self).encode(o)  # Default JSON.

        # Replace any marked-up object ids in the JSON repr with the
        # value returned from the json.dumps() of the corresponding
        # wrapped Python object.
        for match in self.regex.finditer(json_repr):
            # see https://stackoverflow.com/a/15012814/355230
            id = int(match.group(1))
            no_indent = PyObj_FromPtr(id)
            json_obj_repr = json.dumps(no_indent.value, sort_keys=self.__sort_keys)

            # Replace the matched id string with json formatted representation
            # of the corresponding Python object.
            json_repr = json_repr.replace('"{}"'.format(format_spec.format(id)), json_obj_repr)

        return json_repr


def roundoff(value: float) -> float | int:
    # Rounds off with as little decimals as possible without loss, but with a maximum of 3
    rounded = 0
    rounded3 = round(value, 3)
    for decimals in range(4):
        rounded = round(value, decimals)
        if int(rounded * pow(10, decimals)) == rounded3 * pow(10, decimals):
            break
    return int(rounded) if decimals == 0 else rounded


class JNote(BaseModel):
    s: str  # note symbol (characters)
    t: float | int  # trigger time in 4n values
    n: float = Field(exclude=True)  # duration until next note
    d: float | int  # sustain duration
    _sustain: bool = False

    @field_serializer("t", "d", when_used="always")
    def round(self, value: float) -> float | int:
        return roundoff(value)

    def update_duration(self, new_value: float):
        self.n = new_value
        if not self._sustain:
            self.d = new_value

    def update_times(self, prevnote: "JNote", currtime) -> bool:
        """Updates the start time and duration of the note. This has currently only
        effect for grace notes which uses half of the duration of the previous note
        or rest with a maximum of 0.5 units.
        Returns:
            bool: True if the timeline should be updated with the note's duration
        """
        if self.s[0] in ["A", "E", "I", "O", "U"]:
            # Grace note
            max_duration = 0.5
            if not prevnote:
                self.update_duration(max_duration)
            else:
                self.update_duration(min((currtime - prevnote.t) / 2, max_duration))
                # Correct the duration of the previous note if necessary
                overlap = prevnote.n + self.n - (currtime - prevnote.t)
                if overlap > 0:
                    self.update_duration(prevnote.n - overlap)
            # Grace selfs have been converted to 'regular' selfs, so remove capitalization.
            self.t = currtime - self.n
            self.s = self.s.lower()
            return False
        else:
            self.t = currtime
            return True


class JSymbol(BaseModel):
    s: str  # note symbol (characters)
    t: float | int  # trigger time in 4n values
    d: float | int  # sustain duration

    @field_serializer("t", "d", when_used="always")
    def round(self, value: float) -> float | int:
        return roundoff(value)


class JStave(BaseModel):
    position: str
    velocity: list[float, float]
    notes: list[JNote]
    notation: list[JSymbol]


class JSection(BaseModel):
    # Corresponds with a beat
    id: int
    title: str
    starttime: float
    duration: float
    tempo: list[int, int]
    data: list[JStave]


class JSystem(BaseModel):
    # Corresponds with a gongan
    id: int
    title: str
    starttime: float
    duration: float
    tempo: list[int, int]
    data: list[JStave]

    # Add field serializers for more compact layout of JSON output

    @field_serializer("tempo", when_used="always")
    def serialize_tempo(self, tempo: list[int, int]):
        return NoIndent(tempo)

    @field_serializer("data", when_used="always")
    def serialize_data(self, data: list[JStave]):
        return [NoIndent(stave.model_dump(exclude_defaults=True)) for stave in data]


class JScore(BaseModel):
    title: str
    composer: str
    sections: list[JSection]


class JsonCreator:
    """
    Converts a Score object to JSON notation.
    """

    SUSTAIN_DURATION: int = 20

    def __init__(self, title: str, composer: str, run_settings: RunSettings, instrument_positions: set[Position]):
        super().__init__()
        self.run_settings = run_settings
        self.current_beat_id = 0
        self.timelines: dict[Position, int] = {pos: 0 for pos in instrument_positions}
        self.last_notes: dict[Position, JNote | None] = {pos: None for pos in instrument_positions}
        self.jscore = JScore(title=title, composer=composer, sections=[])
        # Dummy beat info needed for initial silence

    def note_to_jnotes(self, note: Note | Pattern) -> list[JNote]:
        if isinstance(note, Note):
            return [
                JNote(
                    s=note.symbol.replace("-", " "),
                    t=0,
                    n=note.note_value,
                    d=note.note_value if (note.sustaintype == SustainType.OFF_ON_NEXT_NOTE) else self.SUSTAIN_DURATION,
                    _sustain=(note.sustaintype == SustainType.SUSTAIN),
                )
            ]
        else:
            notes = []
            for patt_note in note.pattern:
                notes.append(
                    JNote(
                        s=patt_note.symbol.replace("-", " "),
                        t=0,
                        n=patt_note.note_value,
                        d=(
                            patt_note.note_value
                            if (patt_note.sustaintype == SustainType.OFF_ON_NEXT_NOTE)
                            else self.SUSTAIN_DURATION
                        ),
                        _sustain=(patt_note.sustaintype == SustainType.SUSTAIN),
                    )
                )
            return notes

    def notes_to_notation(self, position: Position, notes: list[Note | Pattern]) -> list[JSymbol]:
        curr_time = self.timelines[position]
        jsymbols = []
        for note in notes:
            jsymbols.append(JSymbol(s=note.symbol, t=curr_time, d=note.duration))
            curr_time += note.duration
        return jsymbols

    def group_silences(self, position: Position) -> callable:

        def group_silences_for_pos(reduced: list[JNote], note: JNote) -> list[JNote]:
            pos = position
            prevnote = reduced[-1] if reduced else None
            reduced_cpy = reduced.copy()
            if note.s not in [".", " "]:
                update_timeline = note.update_times(prevnote, self.timelines[pos])
                if update_timeline:
                    self.timelines[pos] += note.n
                reduced_cpy.append(note)
                # if self.last_notes[pos] and self.last_notes[pos]._sustain:  # pylint: disable=protected-access
                #     self.last_notes[pos].d = 20
                self.last_notes[pos] = note
            else:
                if note.s == " " and self.last_notes[pos]:
                    self.last_notes[pos].update_duration(self.last_notes[pos].n + note.n)
                self.timelines[pos] += note.n
            return reduced_cpy

        return group_silences_for_pos

    def aggregate(self, jnotes: list[JNote], position: Position) -> list[JNote]:
        result = reduce(self.group_silences(position), jnotes, [])
        return result

    def velocity2frac(self, velocity: int) -> float:
        return round(velocity / 127, 2)

    def append_beat_info(self, beat: Beat, beat_info: BeatInfo):
        """Appends a beat to the JSON structure."""
        self.current_beat_id += 1
        jsection = JSection(
            id=self.current_beat_id,
            title=beat_info.fullid,
            starttime=round(max(self.timelines.values()), 3),
            duration=beat_info.duration,
            tempo=(beat_info.start_bpm, beat_info.end_bpm),  # NoIndent
            data=[  # NoIndent
                JStave(
                    position=pos,
                    notation=self.notes_to_notation(position=pos, notes=measure.passes[-1].notes),
                    notes=self.aggregate(
                        sum((self.note_to_jnotes(note) for note in measure.passes[-1].notes), []), position=pos
                    ),
                    velocity=(
                        self.velocity2frac(beat_info.start_velocities[pos]),
                        self.velocity2frac(beat_info.end_velocities[pos]),
                    ),
                )
                for pos, measure in beat.measures.items()
            ],
        )
        self.jscore.sections.append(jsection)

    def save_to_json(self):
        """Saves the JSONized score to file. The file is saved in compact form for production."""
        indent = None
        dictized = self.jscore.model_dump()
        if self.run_settings.options.notation_to_midi.run_type is not RunType.PRODUCTION:
            indent = 4
        jsonized = json.dumps(dictized, indent=indent, cls=CompactEncoder)
        with open(self.run_settings.json_out_filepath, "w", encoding="UTF-8") as outfile:
            outfile.writelines(jsonized)
