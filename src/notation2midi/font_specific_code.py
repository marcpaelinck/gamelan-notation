from mido import Message, MetaMessage, MidiTrack, bpm2tempo, tempo2bpm

from src.common.classes import Beat, Character, Score
from src.common.constants import (
    Duration,
    InstrumentPosition,
    InstrumentType,
    Modifier,
    NotationFont,
    Note,
    Octave,
    Stroke,
)
from src.common.utils import CHARACTER_LIST, SYMBOLVALUE_TO_MIDINOTE_LOOKUP
from src.notation2midi.settings import BASE_NOTE_TIME, BASE_NOTES_PER_BEAT


class MidiTrackX(MidiTrack):
    font: NotationFont
    last_note_end_msg = None
    time_since_last_note_end: int = 0
    current_bpm: int = 0
    current_signature: int = 0

    def __init__(self, font: NotationFont):
        self.font = font
        super(MidiTrackX, self).__init__()

    def total_tick_time(self):
        return sum(msg.time for msg in self)

    def update_signature(self, new_signature) -> None:
        if new_signature != self.current_signature:
            self.append(
                MetaMessage(
                    "time_signature",
                    numerator=round(new_signature),
                    denominator=4,
                    clocks_per_click=36,
                    notated_32nd_notes_per_beat=8,
                    time=self.time_since_last_note_end,
                )
            )
            self.time_since_last_note_end = 0
            self.current_signature = new_signature

    def update_tempo(self, new_tempo):
        if new_tempo != self.current_bpm:
            self.append(MetaMessage("set_tempo", tempo=bpm2tempo(new_tempo)))
            self.current_bpm = new_tempo

    def extend_last_note(self, seconds: int) -> None:
        if self.last_note_end_msg:
            beats = round(self.current_bpm * seconds / 60)
            self.last_note_end_msg.time += beats * BASE_NOTE_TIME * BASE_NOTES_PER_BEAT

    def add_note(self, position: InstrumentPosition, character: Character):
        """Converts a note into a midi event

        Args:
            position (InstrumentPosition): The instrument position playing the note.
            note (Character): Note to be processed.

        Raises:
            ValueError: _description_
        """
        if not character.note == Note.NONE:
            midinote = SYMBOLVALUE_TO_MIDINOTE_LOOKUP[
                position.instrumenttype, character.note, character.octave, character.stroke
            ]
            # Set ON and OFF messages for actual note
            self.append(
                Message(
                    type="note_on",
                    channel=midinote.channel,
                    note=midinote.midi,
                    velocity=100,
                    time=self.time_since_last_note_end,
                )
            )
            self.append(
                Message(
                    type="note_off",
                    channel=midinote.channel,
                    note=midinote.midi,
                    velocity=70,
                    time=round(character.duration * BASE_NOTE_TIME),
                )
            )
            self.last_note_end_msg = self[-1]
            self.time_since_last_note_end = round(character.rest_after * BASE_NOTE_TIME)
        # TODO next two ifs can now be combined
        elif character.stroke is Stroke.SILENCE:
            # Increment time since last note ended
            self.time_since_last_note_end += round(character.rest_after * BASE_NOTE_TIME)
        elif character.stroke is Stroke.EXTENSION:
            # Extension of note duration: add duration to last note
            if self.last_note_end_msg:
                self.last_note_end_msg.time += round(character.duration * BASE_NOTE_TIME)
        else:
            raise ValueError(f"Unexpected note value {character.note} {character.octave} {character.stroke}")


def postprocess_font4(score: Score) -> Score:
    # Merge notes with negative value with previous note(s)
    for system in score.systems:
        for beat in system.beats:
            for instrument, stave in beat.staves.items():
                stave_cpy = stave.copy()
                stave.clear()
                for note in stave_cpy:
                    if note.modifier is Modifier.MODIFIER_PREV1:
                        prevnote = stave.pop(-1)
                        stave.append(
                            prevnote.model_copy(update={"duration": note.duration, "rest_after": note.rest_after})
                        )
                    elif note.modifier is Modifier.MODIFIER_PREV2:
                        prev1note = stave.pop(-1)
                        prev2note = stave.pop(-1)
                        new_rest_after = max(0, prev2note.rest_after - note.duration)
                        new_duration = max(0, prev2note.duration - (note.duration - new_rest_after))
                        stave.append(
                            prev2note.model_copy(update={"duration": new_duration, "rest_after": new_rest_after})
                        )
                        stave.append(prev1note.model_copy(update={"duration": note.rest_after}))
                    else:
                        stave.append(note)
            beat.duration = max(sum(note.total_duration for note in notes) for notes in list(beat.staves.values()))


def get_next_note(beat: Beat, position: InstrumentPosition, index: int) -> Character:
    char = next((char for char in beat.staves[position][index + 1 :] if char.note is not Note.NONE), None)
    if not char:
        next_stave = beat.next.staves.get(position, []) if beat.next else []
        char = next((char for char in next_stave if char.note is not Note.NONE), None)
    return char


def apply_ratio(note: Character, ratio_note: Character) -> tuple[Duration, Duration]:
    total_duration = note.total_duration
    new_duration = total_duration * round(ratio_note.duration)
    new_time_after = total_duration - new_duration
    return new_duration, new_time_after


def postprocess_font5(score: Score) -> Score:
    for iteration in [1, 2]:  # Needed for correct processing of grace notes. See explanation below.
        for system in score.systems:
            for beat in system.beats:
                for instr_position, stave in beat.staves.items():
                    new_stave = list()
                    for index, note in enumerate(stave):
                        match note.modifier:
                            case Modifier.MUTE | Modifier.ABBREVIATE:
                                prevnote = new_stave.pop(-1)
                                if prevnote.note == Note.BYONG:
                                    new_note, new_stroke = (
                                        (Note.BYOT, Stroke.OPEN)
                                        if note.modifier == Modifier.MUTE
                                        else (Note.JET, Stroke.MUTED)
                                    )
                                    new_duration, new_rest_after = prevnote.duration, prevnote.rest_after
                                elif note.modifier == Modifier.ABBREVIATE:
                                    new_duration, new_rest_after = apply_ratio(prevnote, note)
                                    new_note, new_stroke = prevnote.note, prevnote.stroke
                                else:
                                    new_duration, new_rest_after = prevnote.duration, prevnote.rest_after
                                    new_note = prevnote.note
                                    new_stroke = (
                                        Stroke.MUTED
                                        if (instr_position, new_note, prevnote.octave, Stroke.MUTED)
                                        in list(score.midi_notes_dict.keys())
                                        else prevnote.stroke
                                    )
                                new_stave.append(
                                    prevnote.model_copy(
                                        update={
                                            "symbol": prevnote.symbol + note.symbol,
                                            "note": new_note,
                                            "stroke": new_stroke,
                                            "duration": new_duration,
                                            "rest_after": new_rest_after,
                                        }
                                    )
                                )
                            case Modifier.HALF_NOTE | Modifier.QUARTER_NOTE:
                                prevnote = new_stave.pop(-1)
                                new_duration = prevnote.duration * note.duration
                                new_rest_after = prevnote.rest_after * note.duration
                                new_stave.append(
                                    prevnote.model_copy(
                                        update={
                                            "symbol": prevnote.symbol + note.symbol,
                                            "duration": new_duration,
                                            "rest_after": new_rest_after,
                                        }
                                    )
                                )
                            case Modifier.OCTAVE_0 | Modifier.OCTAVE_2:
                                prevnote = new_stave.pop(-1)
                                new_stave.append(
                                    prevnote.model_copy(
                                        update={"symbol": prevnote.symbol + note.symbol, "octave": note.octave}
                                    )
                                )
                            case Modifier.SUBTRACT_FROM_PREV:  # Grace notes
                                if iteration == 1:
                                    # Append the grace note during iteration 1 so that it can be processed in iteration 2.
                                    # We need to wait until all modifiers of the next node have been applied before proceeding.
                                    # See also the next remark.
                                    new_stave.append(note)
                                if iteration == 2:
                                    # The symbol of grace notes does not have information about its octave.
                                    # In order to determine the correct octave, we assume that grace notes are always as "close"
                                    # as possible to the following note.
                                    # In order to get the correct octave of the following note, we need to wait until its modifiers
                                    # have been processed. This is why we wait until the second iteration to process grace notes.
                                    if note.octave:
                                        next_note = get_next_note(beat, instr_position, index)
                                        if next_note:
                                            # Create a list of notes in the instrument's range with indices
                                            instr_range = {
                                                (note, oct): idx
                                                for idx, (note, oct, stroke) in enumerate(
                                                    score.position_range_lookup[instr_position]
                                                )
                                                if stroke == score.position_range_lookup[instr_position][0][2]
                                            }
                                            next_note_idx = instr_range[next_note.note, next_note.octave]
                                            possible_octaves = [
                                                (o, abs(idx - next_note_idx))
                                                for (n, o), idx in instr_range.items()
                                                if n == note.note
                                            ]
                                            octave = (
                                                next(
                                                    (
                                                        o
                                                        for o, diff in possible_octaves
                                                        if diff == min([diff for _, diff in possible_octaves])
                                                    ),
                                                    None,
                                                )
                                                or note.octave
                                            )
                                    else:
                                        octave = None
                                    prevnote = new_stave.pop(-1)
                                    new_rest_after = max(0, prevnote.rest_after - note.duration)
                                    new_duration = max(0, prevnote.duration - (note.duration - new_rest_after))
                                    new_stave.append(
                                        prevnote.model_copy(
                                            update={"duration": new_duration, "rest_after": new_rest_after}
                                        )
                                    )
                                    new_stave.append(note.model_copy(update={"octave": octave}))
                            case _:
                                new_stave.append(note)
                    stave.clear()
                    stave.extend(new_stave)

                beat.duration = max(sum(note.total_duration for note in notes) for notes in list(beat.staves.values()))


def postprocess(score: Score) -> Score:
    if score.source.font is NotationFont.BALIMUSIC4:
        postprocess_font4(score)
    elif score.source.font is NotationFont.BALIMUSIC5:
        postprocess_font5(score)
    else:
        raise ValueError(f"Unexpected font value {score.source.font}")


def create_character(
    note: Note,
    octave: int,
    stroke: Stroke,
    duration: float,
    rest_after: float,
    symbol: str = "",
    unicode: str = "",
    symbol_description: str = "",
    balifont_symbol_description: str = "",
    modifier: Modifier = Modifier.NONE,
    description: str = "",
) -> Character:
    Character(
        note=note,
        octave=octave,
        stroke=stroke,
        duration=duration,
        rest_after=rest_after,
        symbol=symbol,
        unicode=unicode,
        symbol_description=symbol_description,
        balifont_symbol_description=balifont_symbol_description,
        modifier=modifier,
        description=description,
    )


def get_character(
    note: Note,
    octave: Octave,
    stroke: Stroke,
    duration: Duration,
    rest_after: Duration,
    symbol: str,
    font: NotationFont,
) -> Character:
    """Returns the first character with the given characteristics

    Args:
        note (Note): _description_
        octave (Octave): _description_
        stroke (Stroke): _description_
        duration (Duration): _description_
        rest_after (Duration): _description_
        symbol (str): _description_

    Returns:
        Character: a copy of a Character from the character list if a match is found, otherwise an newly created Character object.
    """
    char = next((char for char in CHARACTER_LIST if char.matches(note, octave, stroke, duration, rest_after)), None)
    char = char or next((char for char in CHARACTER_LIST if char.matches(note, octave, stroke, 1, 0)), None)
    char = char or next((char for char in CHARACTER_LIST if char.matches(note, 1, stroke, 1, 0)), None)
    char = char or next((char for char in CHARACTER_LIST if char.matches(note, 1, Stroke.OPEN, 1, 0)), None)
    char = char or create_character(note, octave, stroke, duration, rest_after, symbol="")
    char_symbol = char.symbol
    additional_symbol = ""
    if font is NotationFont.BALIMUSIC5 and octave != 1:
        if symbol[0] in "1234567" and char_symbol in "ioeruas":
            # replace regular note symbol with grace note equivalent
            char_symbol = "1234567"["ioeruas".find(char_symbol)]
        additional_symbol = "," if octave == 0 else "<"

    return char.model_copy(
        update={
            "symbol": char_symbol + additional_symbol + symbol[1:],
            "octave": octave,
            "stroke": stroke,
            "duration": duration,
            "rest_after": rest_after,
        }
    )
