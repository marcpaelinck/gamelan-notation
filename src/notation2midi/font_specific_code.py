from src.common.classes import Beat, Character, Score
from src.common.constants import (
    Duration,
    InstrumentPosition,
    Modifier,
    NotationFont,
    Note,
    Octave,
    Stroke,
)
from src.common.utils import CHARACTER_LIST
from src.notation2midi.settings import BASE_NOTE_TIME

# ==================== BALI MUSIC 4 FONT =====================================


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


# ==================== BALI MUSIC 5 FONT =====================================

TREMOLO_NR_OF_NOTES_PER_QUARTERNOTE: int = 3  # should be a divisor of BASE_NOTE_TIME
# Next values are in 1/BASE_NOTE_TIME. E.g. if BASE_NOTE_TIME=24, then 24 is a standard note duration.
# Should also be an even number so that alternating note patterns end on the second note.
TREMOLO_ACCELERATING_PATTERN: list[int] = [48, 40, 32, 26, 22, 18, 14, 10, 10, 10, 10, 10]
TREMOLO_ACCELERATING_VELOCITY: list[int] = [100] * (len(TREMOLO_ACCELERATING_PATTERN) - 5) + [90, 85, 80, 75, 70]


def apply_ratio(note: Character, ratio_note: Character) -> tuple[Duration, Duration]:
    total_duration = note.total_duration
    new_duration = total_duration * ratio_note.duration
    new_time_after = total_duration - new_duration
    return new_duration, new_time_after


def get_nearest_octave(char: Character, other_char: Character, noterange: list[tuple[Note, Octave]]) -> Octave:
    """Returns the octave for char that minimizes the distance between the two character notes.

    Args:
        char (Character): character for which to optimize the octave
        other_char (Character): reference character
        noterange (list[tuple[Note, Octave]]): available note range

    Returns:
        Octave: the octave that puts char nearest to other_char
    """
    next_note_idx = noterange.index((other_char.note, other_char.octave))
    octave = None
    best_distance = 99
    for offset in [0, 1, -1]:
        new_octave = other_char.octave + offset
        if (char.note, new_octave) in noterange and (
            new_distance := abs(noterange.index((char.note, new_octave)) - next_note_idx)
        ) < best_distance:
            octave = new_octave
            best_distance = min(new_distance, best_distance)
    return octave


def remove_from_last_note_to_end(stave: list[Character]) -> tuple[Character | None, list[Character]]:
    """Searches for the last note character in stave and removes this note and all characters following it.

    Args:
        stave (list[Character]): list to be searched.

    Returns:
        tuple[Character | None, list[Character]]: The last note if found and the characters following it.
    """
    modifiers = []
    note = None
    while stave and not note:
        element = stave.pop(-1)
        if element.note is not Note.NONE:
            note = element
        else:
            modifiers.append(element)
    return note, modifiers


def generate_accelerated_tremolo(stave: dict[InstrumentPosition, list[Character]]):
    """Generates the note sequence for an accelerated tremolo

    Args:
        stave (dict[InstrumentPosition, list[Character]]): _description_
    """
    notes = []
    notes.append(stave.pop(-1))
    # remove the previous note from new_stave if it is also TREMOLO_ACCELERATING
    if stave and stave[-1].modifier is Modifier.TREMOLO_ACCELERATING:
        stave.pop(-1)
        notes.insert(0, stave.pop(-1))
    durations = [i / BASE_NOTE_TIME for i in TREMOLO_ACCELERATING_PATTERN]
    note_idx = 0
    for duration, velocity in zip(durations, TREMOLO_ACCELERATING_VELOCITY):
        stave.append(notes[note_idx].model_copy(update={"duration": duration, "velocity": velocity}))
        note_idx = (note_idx + 1) % len(notes)


def postprocess_font5(score: Score) -> Score:
    for iteration in [1, 2]:  # Needed for correct processing of grace notes. See explanation below.
        for system in score.systems:
            for beat in system.beats:
                for position, stave in beat.staves.items():
                    instr_range = [
                        (note, oct)
                        for (note, oct, stroke) in score.position_range_lookup[position]
                        if stroke == score.position_range_lookup[position][0][2]
                    ]

                    new_stave = list()
                    for index, note in enumerate(stave):
                        match note.modifier:
                            case Modifier.MUTE | Modifier.ABBREVIATE:
                                # Mute / abbreviate preceding note.
                                # Check if there is a separate MIDI entry for the muted/abbreviated variant of this note.
                                prevnote = new_stave.pop(-1)
                                if (
                                    position.instrumenttype,
                                    prevnote.note,
                                    prevnote.octave,
                                    note.stroke,
                                ) in score.midi_notes_dict:
                                    # Midi entry found: keep previous note durations and change its stroke type
                                    new_duration, new_rest_after = prevnote.duration, prevnote.rest_after
                                    new_stroke = note.stroke
                                else:
                                    # No separate MIDI entry: emulate the stroke by modifying the note duration
                                    new_duration, new_rest_after = apply_ratio(prevnote, note)
                                    new_stroke = prevnote.stroke
                                new_stave.append(
                                    prevnote.model_copy(
                                        update={
                                            "symbol": prevnote.symbol + note.symbol,
                                            "stroke": new_stroke,
                                            "duration": new_duration,
                                            "rest_after": new_rest_after,
                                        }
                                    )
                                )
                            case Modifier.HALF_NOTE | Modifier.QUARTER_NOTE:
                                # Reduce the note duration of the preceding note.
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
                                # Modify the octave of the preceding note.
                                prevnote = new_stave.pop(-1)
                                new_stave.append(
                                    prevnote.model_copy(
                                        update={"symbol": prevnote.symbol + note.symbol, "octave": note.octave}
                                    )
                                )
                            case Modifier.GRACE_NOTE:
                                # A grace note is both a note and a modifyer.
                                # 1. Subtract its length from the preceding note.
                                # 2. Determine its octave (grace notes can't be combined with an octave indicator).
                                if iteration == 1:
                                    # Do not process the grace note during iteration 1: put it back so that it can be processed
                                    # in iteration 2. We need to wait until all modifiers of the next node have been applied.
                                    # See next remark.
                                    new_stave.append(note)
                                if iteration == 2:
                                    # The symbol of grace notes does not have information about its octave. In order to determine the
                                    # correct octave, we assume that grace notes are always as "close" as possible to the following note.
                                    if note.octave and (next_note := get_next_note(beat, position, index)):
                                        octave = get_nearest_octave(note, next_note, instr_range)
                                    else:
                                        octave = note.octave
                                    # Subtract the duration of the grace note from its predecessor
                                    prevnote = new_stave.pop(-1)
                                    new_rest_after = max(0, prevnote.rest_after - note.duration)
                                    new_duration = max(0, prevnote.duration - (note.duration - new_rest_after))
                                    new_stave.append(
                                        prevnote.model_copy(
                                            update={"duration": new_duration, "rest_after": new_rest_after}
                                        )
                                    )
                                    # Add the grace note with the correct octave
                                    new_stave.append(note.model_copy(update={"octave": octave}))
                            case Modifier.TREMOLO:
                                if iteration == 1:
                                    new_stave.append(note)
                                if iteration == 2:
                                    prevnote = new_stave.pop(-1)
                                    nr_of_notes = round(prevnote.duration * TREMOLO_NR_OF_NOTES_PER_QUARTERNOTE)
                                    duration = prevnote.duration / nr_of_notes
                                    for _ in range(nr_of_notes):
                                        new_stave.append(prevnote.model_copy(update={"duration": duration}))
                            case Modifier.TREMOLO_ACCELERATING:
                                # If the next two characters are also a TREMOLO_ACCELERATING NOTE, then wait for that modifier to be selected.
                                if iteration == 1:
                                    new_stave.append(note)
                                if iteration == 2:
                                    if (
                                        len(stave) >= index + 3
                                        and stave[index + 1].note is not Note.NONE
                                        and stave[index + 2].modifier is Modifier.TREMOLO_ACCELERATING
                                    ):
                                        new_stave.append(note)
                                    else:
                                        generate_accelerated_tremolo(new_stave)
                            case _:
                                new_stave.append(note)
                    stave.clear()
                    stave.extend(new_stave)

                beat.duration = max(sum(note.total_duration for note in notes) for notes in list(beat.staves.values()))


def postprocess(score: Score) -> Score:
    """Processes the modifier characters. These are characters that change properties of the preceding note.
    Usually these characters don't have an intrinsic value are discarded after having been processed.
    The meaning and effect of modifiers is font specific.

    Args:
        score (Score): The score

    Raises:
        ValueError: _description_

    Returns:
        Score: _description_
    """
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
    return Character(
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
        font(NotationFont): the font used

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
    if font is NotationFont.BALIMUSIC5:
        # symbol can consist of more than one character: a note symbol followed by one or more modifiers
        if symbol[0] in "1234567" and char_symbol in "ioeruas":
            # replace regular note symbol with grace note equivalent
            char_symbol = "1234567"["ioeruas".find(char_symbol)]
        additional_symbol = "," if octave == 0 else "<" if octave == 2 else ""

    return char.model_copy(
        update={
            "symbol": char_symbol + additional_symbol + symbol[1:],
            "octave": octave,
            "stroke": stroke,
            "duration": duration,
            "rest_after": rest_after,
        }
    )
