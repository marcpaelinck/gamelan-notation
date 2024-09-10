from src.common.classes import Beat, Note, Score
from src.common.constants import (
    Duration,
    InstrumentPosition,
    Modifier,
    NotationFont,
    Octave,
    Pitch,
    Stroke,
)
from src.common.utils import NOTE_LIST
from src.notation2midi.settings import BASE_NOTE_TIME

# ==================== BALI MUSIC 4 FONT =====================================


def postprocess_font4(score: Score) -> Score:
    # Merge notes with negative value with previous note(s)
    for gongan in score.gongans:
        for beat in gongan.beats:
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


def get_next_note(beat: Beat, position: InstrumentPosition, index: int) -> Note:
    note = next((note for note in beat.staves[position][index + 1 :] if note.pitch is not Pitch.NONE), None)
    if not note:
        next_stave = beat.next.staves.get(position, []) if beat.next else []
        note = next((note for note in next_stave if note.pitch is not Pitch.NONE), None)
    return note


# ==================== BALI MUSIC 5 FONT =====================================

TREMOLO_NR_OF_NOTES_PER_QUARTERNOTE: int = 3  # should be a divisor of BASE_NOTE_TIME
# Next values are in 1/BASE_NOTE_TIME. E.g. if BASE_NOTE_TIME=24, then 24 is a standard note duration.
# Should also be an even number so that alternating note patterns end on the second note.
TREMOLO_ACCELERATING_PATTERN: list[int] = [48, 40, 32, 26, 22, 18, 14, 10, 10, 10, 10, 10]
TREMOLO_ACCELERATING_VELOCITY: list[int] = [100] * (len(TREMOLO_ACCELERATING_PATTERN) - 5) + [90, 80, 70, 60, 50]


def apply_ratio(note: Note, ratio_note: Note) -> tuple[Duration, Duration]:
    total_duration = note.total_duration
    new_duration = total_duration * ratio_note.duration
    new_time_after = total_duration - new_duration
    return new_duration, new_time_after


def get_nearest_octave(note: Note, other_note: Note, noterange: list[tuple[Pitch, Octave]]) -> Octave:
    """Returns the octave for note that minimizes the distance between the two note pitches.

    Args:
        note (Note): note for which to optimize the octave
        other_note (Note): reference nte
        noterange (list[tuple[Pitch, Octave]]): available note range

    Returns:
        Octave: the octave that puts the pitch of note nearest to that of other_note
    """
    next_note_idx = noterange.index((other_note.pitch, other_note.octave))
    octave = None
    best_distance = 99
    for offset in [0, 1, -1]:
        new_octave = other_note.octave + offset
        if (note.pitch, new_octave) in noterange and (
            new_distance := abs(noterange.index((note.pitch, new_octave)) - next_note_idx)
        ) < best_distance:
            octave = new_octave
            best_distance = min(new_distance, best_distance)
    return octave


def remove_from_last_note_to_end(stave: list[Note]) -> tuple[Note | None, list[Note]]:
    """Searches for the last note in stave and removes this note and all notes following it.

    Args:
        stave (list[Note]): list to be searched.

    Returns:
        tuple[Note | None, list[Note]]: The last note if found and the notes following it.
    """
    modifiers = []
    note = None
    while stave and not note:
        element = stave.pop(-1)
        if element.pitch is not Pitch.NONE:
            note = element
        else:
            modifiers.append(element)
    return note, modifiers


def generate_accelerated_tremolo(stave: dict[InstrumentPosition, list[Note]]):
    """Generates the note sequence for an accelerated tremolo

    Args:
        stave (dict[InstrumentPosition, list[Note]]): _description_
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
        for gongan in score.gongans:
            for beat in gongan.beats:
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
                                    prevnote.pitch,
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
                                # If the next two note objects also define a TREMOLO_ACCELERATING NOTE, then wait for that modifier to be selected.
                                if iteration == 1:
                                    new_stave.append(note)
                                if iteration == 2:
                                    if (
                                        len(stave) >= index + 3
                                        and stave[index + 1].pitch is not Pitch.NONE
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
    """Processes the modifier notes. Modifiers are Note objects that change properties of the preceding note.
    Usually these objects don't have a pitch value (Pitch.NONE) and are discarded after having been processed.
    The meaning and effect of modifiers is font specific.

    Args:
        score (Score): The score

    Raises:
        ValueError: _description_

    Returns:
        Score: _description_
    """
    if score.settings.font.font_version is NotationFont.BALIMUSIC4:
        postprocess_font4(score)
    elif score.settings.font.font_version is NotationFont.BALIMUSIC5:
        postprocess_font5(score)
    else:
        raise ValueError(f"Unexpected font value {score.settings.font.font_version}")


def create_note(
    pitch: Pitch,
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
) -> Note:
    return Note(
        pitch=pitch,
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


def get_note(
    pitch: Pitch,
    octave: Octave,
    stroke: Stroke,
    duration: Duration,
    rest_after: Duration,
    symbol: str,
    font: NotationFont,
) -> Note:
    """Returns the first note with the given characteristics

    Args:
        pitch (Pitch): _description_
        octave (Octave): _description_
        stroke (Stroke): _description_
        duration (Duration): _description_
        rest_after (Duration): _description_
        symbol (str): _description_
        font(NotationFont): the font used

    Returns:
        Note: a copy of a Note from the note list if a match is found, otherwise an newly created Note object.
    """
    note = next((note for note in NOTE_LIST if note.matches(pitch, octave, stroke, duration, rest_after)), None)
    note = note or next((note for note in NOTE_LIST if note.matches(pitch, octave, stroke, 1, 0)), None)
    note = note or next((note for note in NOTE_LIST if note.matches(pitch, 1, stroke, 1, 0)), None)
    note = note or next((note for note in NOTE_LIST if note.matches(pitch, 1, Stroke.OPEN, 1, 0)), None)
    note = note or create_note(pitch, octave, stroke, duration, rest_after, symbol="")
    note_symbol = note.symbol
    additional_symbol = ""
    if font is NotationFont.BALIMUSIC5:
        # symbol can consist of more than one character: a pitch symbol followed by one or more modifier symbols
        if symbol[0] in "1234567" and note_symbol in "ioeruas":
            # replace regular pitch symbol with grace note equivalent
            note_symbol = "1234567"["ioeruas".find(note_symbol)]
        additional_symbol = "," if octave == 0 else "<" if octave == 2 else ""

    return note.model_copy(
        update={
            "symbol": note_symbol + additional_symbol + symbol[1:],
            "octave": octave,
            "stroke": stroke,
            "duration": duration,
            "rest_after": rest_after,
        }
    )
