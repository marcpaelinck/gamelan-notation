from src.common.classes import MidiNote
from src.common.constants import InstrumentType, Stroke
from src.settings.settings import RUN_SETTINGS


def truncated_name(components: list[str]) -> str:
    """Creates a name for the sample / midi note, based on the given values.
    Names longer than 20 characters are truncated due to SoundFont limitations.

    Args:
        components (list[str]): constituents for the name

    Returns:
        str: _description_
    """
    MAXLENGTH = 20
    # excess is the number of characters to delete (corrected for the space separators between the components).
    excess = max(sum(len(part) for part in components) - (MAXLENGTH - len(components) + 1), 0)
    # truncate the longest components of the name if excess > 0.
    for _ in range(excess):
        # find the longest component and remove its last character
        idx = components.index(max(components, key=len))
        components[idx] = components[idx][:-1]
    return " ".join(components)


def sample_notes_lookup(midi_dict: dict[InstrumentType, list[MidiNote]]) -> dict[str, MidiNote]:
    # Make a list of unique sample file names
    sample_list = {note.sample for notelist in midi_dict.values() for note in notelist}
    # Create a dict {file name -> list[midinote]}
    return {
        sample: [note for notelist in midi_dict.values() for note in notelist if note.sample == sample]
        for sample in sample_list
        if sample
    }


def sample_name_lookup(midi_dict: dict[InstrumentType, MidiNote]) -> dict[MidiNote, str]:
    sample_name_dict = sample_notes_lookup(midi_dict)
    # Create a dict {file name -> unique name}
    sample_lookup = dict()
    for sample, notes in sample_name_dict.items():
        items = [
            notes[0].instrumenttype.value,
            notes[0].pitch.value + (str(notes[0].octave) if notes[0].octave != None else ""),
        ]
        if Stroke.OPEN not in [note.stroke.value for note in notes]:
            items.append(notes[0].stroke.value)
        sample_lookup[sample] = truncated_name(items)

    if len(set(sample_lookup.values())) != len(sample_lookup.values()):
        raise Exception("Duplicate sample names were generated.")
    return sample_lookup


if __name__ == "__main__":
    run_settings = RUN_SETTINGS
