from typing import Callable

from src.common.classes import Instrument, Note
from src.common.constants import Stroke
from src.settings.classes import SettingsMidiInfo


def notes_to_notation(measure: list[Note]) -> str:
    """Returns the concatenated symbols of the given list of notes"""
    try:
        return "".join([note.symbol for note in measure])
    except:  # pylint: disable=bare-except
        return ""


def update_grace_notes_octaves(measure: list[Note]) -> list[Note]:
    """Updates the octave of any grace note found in measure. The octave is set by checking
        the note that follows the grace minimizing the 'interval' between both notes.

    Args:
        measure (list[Note]): list of notes that should be checked for grace notes.
    Raises:
        ValueError: if a grace note is not followed by a melodic note.
    Returns:
        list[Note]: Te updated llist
    """

    updated_measure = []

    for note, nextnote in zip(measure.copy(), measure.copy()[1:] + [None]):
        if note.stroke == Stroke.GRACE_NOTE and note.is_melodic():
            if not nextnote or not nextnote.is_melodic:
                raise ValueError("Grace note not followed by melodic note in %s" % notes_to_notation(measure))
            tones = Instrument.get_tones_within_range(note.to_tone(), note.position, match_octave=False)
            # pylint: disable=cell-var-from-loop
            nearest = sorted(tones, key=lambda x: abs(Instrument.interval(x, nextnote.to_tone())))[0]
            # pylint: enable=cell-var-from-loop
            nearest_grace_note = note.model_copy_x(octave=nearest.octave)
            updated_measure.append(nearest_grace_note)
        else:
            updated_measure.append(note)

    return updated_measure


def generate_tremolo(measure: list[Note], midi_settings: SettingsMidiInfo, errorlogger: Callable = None) -> list[Note]:
    """Generates the note sequence for a tremolo.
        TREMOLO: The duration and pitch will be that of the given note.
        TREMOLO_ACCELERATING: The pitch will be that of the given note(s), the duration will be derived
        from the TREMOLO_ACCELERATING_PATTERN.
        The generated notes are marked as 'autogenerated'. This value will be used when generating
        (PDF) notation from the score object.

            Args:
        notes (list[Note]): One or two notes on which to base the tremolo (piitch only)

    Returns:
        list[Note]: The resulting notes
    """
    updated_measure = []

    while measure:
        # Scan the measure for tremolo notes
        tremolo_notes = []
        note = measure.pop(0)
        if not note.stroke in (Stroke.TREMOLO, Stroke.TREMOLO_ACCELERATING):
            updated_measure.append(note)
            continue
        tremolo_notes.append(note)
        if measure and note.stroke is Stroke.TREMOLO_ACCELERATING and measure[0].stroke is Stroke.TREMOLO_ACCELERATING:
            # Two successive TREMOLO_ACCELERATING notes will be processed together
            note = measure.pop(0)
            tremolo_notes.append(note)

        # Generate the tremolo pattern

        generated_notes = []

        if tremolo_notes[0].stroke is Stroke.TREMOLO:
            note = tremolo_notes[0]
            nr_of_notes = round(note.duration * midi_settings.tremolo.notes_per_quarternote)
            duration = note.duration / nr_of_notes
            for count in range(nr_of_notes):
                # Mark the additional tremolo_notes as 'autogenerated': this will be used when generating (PDF) notation from the score object.
                generated_notes.append(note.model_copy(update={"duration": duration, "autogenerated": count > 0}))
        elif tremolo_notes[0].stroke is Stroke.TREMOLO_ACCELERATING:
            durations = [i / midi_settings.base_note_time for i in midi_settings.tremolo.accelerating_pattern]
            note_idx = 0  # Index of the next note to select from the `tremolo_notes` list
            for count, (duration, velocity) in enumerate(zip(durations, midi_settings.tremolo.accelerating_velocity)):
                generated_notes.append(
                    # tremolo_notes[note_idx] if count < len(tremolo_notes) else
                    tremolo_notes[note_idx].model_copy(
                        update={"duration": duration, "velocity": velocity, "autogenerated": count > 0}
                    )
                )
                note_idx = (note_idx + 1) % len(tremolo_notes)
        elif errorlogger:
            errorlogger("Unexpected tremolo type %s.", tremolo_notes[0].stroke)

        updated_measure.extend(generated_notes)

    return updated_measure
