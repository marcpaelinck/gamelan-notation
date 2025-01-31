from typing import Callable

from src.common.classes import Instrument, Note
from src.common.constants import InstrumentGroup, Pitch, Stroke
from src.settings.classes import RunSettings


def update_grace_notes_octaves(notes: list[Note], group: InstrumentGroup):
    """Modifies the octave of grace notes to match the note that follows.
    The octave is set to minimise the 'distance' between both notes.
    Args:
        notation_dict (NotationDict): The notation
        group (InstrumentGroup): needed to determine the "nearest note".
    """
    for note, nextnote in zip(notes.copy(), notes.copy()[1:]):
        if note.stroke == Stroke.GRACE_NOTE and note.is_melodic():
            tones = Instrument.get_tones_within_range(note.to_tone(), note.position, match_octave=False)
            nearest = sorted(tones, key=lambda x: abs(Instrument.interval(x, nextnote.to_tone())))[0]
            nearest_grace_note = note.copy_with_changes(octave=nearest.octave)
            notes[notes.index(note)] = nearest_grace_note


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
