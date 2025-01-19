from typing import Callable

from src.common.classes import Note
from src.common.constants import InstrumentGroup, Pitch, Stroke
from src.settings.classes import RunSettings


def get_nearest_note(note: Note, other_note: Note, group: InstrumentGroup) -> Note:
    """Returns the octave for note that minimizes the distance between the two note pitches.

    Args:
        note (Note): note for which to optimize the octave
        other_note (Note): reference nte
        noterange (list[tuple[Pitch, Octave]]): available note range

    Returns:
        Octave: the octave that puts the pitch of note nearest to that of other_note
    """

    # Nothing if either note is non-melodic (reyong can have both types of notes)
    if not note.octave or not other_note.octave:
        return note

    def index(note: Note) -> int:
        noterange = (
            [Pitch.DING, Pitch.DONG, Pitch.DENG, Pitch.DEUNG, Pitch.DUNG, Pitch.DANG, Pitch.DAING]
            if group is InstrumentGroup.SEMAR_PAGULINGAN
            else [Pitch.DING, Pitch.DONG, Pitch.DENG, Pitch.DUNG, Pitch.DANG]
        )
        return noterange.index(note.pitch) + len(noterange) * note.octave

    if not note.pitch or not other_note.pitch or other_note.octave == None:
        raise Exception(f"Can't set octave for grace note {note}")

    next_note_idx = index(other_note)
    nearest_note = None
    best_distance = 999
    for offset in [0, 1, -1]:
        new_octave = other_note.octave + offset
        if (try_note := note.model_copy(update={"octave": new_octave})) and (
            new_distance := abs(index(try_note) - next_note_idx)
        ) < best_distance:
            best_distance = min(new_distance, best_distance)
            nearest_note = try_note
    return nearest_note


def update_grace_notes_octaves(notes: list[Note], group: InstrumentGroup):
    """Modifies the octave of grace notes to match the note that follows.
    The octave is set to minimise the 'distance' between both notes.
    Args:
        notation_dict (NotationDict): The notation
        group (InstrumentGroup): needed to determine the "nearest note".
    """
    for note, nextnote in zip(notes.copy(), notes.copy()[1:]):
        if note.stroke == Stroke.GRACE_NOTE:
            new_note = get_nearest_note(note=note, other_note=nextnote, group=group)
            notes[notes.index(note)] = new_note


def generate_tremolo(
    notes: list[Note], midi_settings: RunSettings.MidiInfo, errorlogger: Callable = None
) -> list[Note]:
    """Generates the note sequence for a tremolo.
        TREMOLO: The duration and pitch will be that of the given note.
        TREMOLO_ACCELERATING: The pitch will be that of the given note(s), the duration will be derived
        from the TREMOLO_ACCELERATING_PATTERN.

    Args:
        notes (list[Note]): One or two notes on which to base the tremolo (piitch only)

    Returns:
        list[Note]: The resulting notes
    """
    tremolo_notes = []

    if notes[0].stroke is Stroke.TREMOLO:
        note = notes[0]
        nr_of_notes = round(note.duration * midi_settings.tremolo.notes_per_quarternote)
        duration = note.duration / nr_of_notes
        for _ in range(nr_of_notes):
            tremolo_notes.append(note.model_copy(update={"duration": duration}))
    elif notes[0].stroke is Stroke.TREMOLO_ACCELERATING:
        durations = [i / midi_settings.base_note_time for i in midi_settings.tremolo.accelerating_pattern]
        note_idx = 0  # Index of the next note to select from the `notes` list
        for duration, velocity in zip(durations, midi_settings.tremolo.accelerating_velocity):
            tremolo_notes.append(notes[note_idx].model_copy(update={"duration": duration, "velocity": velocity}))
            note_idx = (note_idx + 1) % len(notes)
    elif errorlogger:
        errorlogger(f"Unexpected tremolo type {notes[0].stroke}.")

    return tremolo_notes
