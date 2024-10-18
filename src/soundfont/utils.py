from src.common.classes import MidiNote


def sample_name(note: MidiNote) -> str:
    """Creates a name for the sample / midi note, based on the given values.
    Names longer than 20 characters are truncated.

    Args:
        instrumenttype (str): _description_
        pitch (int): _description_
        octave (int | None): _description_
        stroke (str): _description_

    Returns:
        str: _description_
    """
    MAXLENGTH = 20
    octave_str = str(note.octave) if note.octave is not None else ""
    components = [note.instrumenttype.name, " ", note.pitch, octave_str, " ", note.stroke.name]
    surplus = max(sum(len(part) for part in components) - MAXLENGTH, 0)
    # truncate the longest components of the name if MAXLENGTH is exceeded.
    for _ in range(surplus):
        # find the longest component and remove its last character
        idx = components.index(max(components, key=len))
        components[idx] = components[idx][:-1]
    return "".join(components)
