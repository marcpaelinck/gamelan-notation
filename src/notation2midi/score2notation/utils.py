from reportlab.pdfbase.pdfmetrics import stringWidth

from src.common.classes import Gongan, Note
from src.common.constants import DEFAULT, InstrumentType, Position, Stroke
from src.common.metadata_classes import GonganType, MetaDataSwitch


def measure_to_str(notes: list[Note]) -> str:
    """Converts the note objects to notation symbols.
    Replaces characters that are incompatible with HTML/XML content to compatible strings.
    Args:
        notes (list[Note]): Content that should be converted.
    Returns:
        str: HTML/XML compatible representation of the notation.
    """
    if not notes:
        return ""
    notechars = "".join(note.symbol for note in notes).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    return notechars


def clean_staves(gongan: Gongan) -> dict[Position, list[list[Note]]]:
    """Removes staves that consist only of rests (silence or note extension)
       Removes autogenerated notes (e.g. created to emulate tremolo stroke or WAIT metadata).
    Args:
        gongan (Gongan): The congan that should be 'cleaned'.
    Returns:
        dict[Position, list[list[Note]]]: The gongan in tabular form.
    """
    if not gongan.beats:
        return dict()
    staves = {
        position: [
            [note for note in beat.measures[position].passes[DEFAULT].notes if not note.autogenerated]
            for beat in gongan.beats
            # skip beats that are completely autogenerated (e.g. generated from WAIT metadata)
            if not all(
                note.autogenerated for measure in beat.measures.values() for note in measure.passes[DEFAULT].notes
            )
        ]
        for position in gongan.beats[0].measures.keys()
    }
    return staves


def stringWidth_fromNotes(measure: list[Note], fontName: str, fontSize: int) -> int:
    """Determines the width of a notation string. This function corrects the value returned by
       the stringWidth method, which does not process grace notes correctly.
       this is possibly due to the negative width of grace notes with the `Bali Font 5` font.
    Args:
        measure (list[Note]): Notes for which to determine the width of the notation.
        fontName (str):
        fontSize (int):
    Returns:
        int: the width in points.
    """
    char_count = len([note for note in measure if note.stroke != Stroke.GRACE_NOTE])
    return stringWidth("a" * char_count, fontName, fontSize)


def _to_aggregated_tags(positions: list[Position]) -> list[str]:
    """Returns a lowercase value of the instrument names. This function is used to
       for the values of the `positions` parameter of metadata items.
    Args:
        positions (list[Position]):
    Returns:
        list[str]: list of lowercase values for the position names.
    """
    tags = set(pos.instrumenttype.lower() for pos in positions)
    gangsa = {InstrumentType.PEMADE.lower(), InstrumentType.KANTILAN.lower()}
    if gangsa.issubset(tags):
        tags = tags.difference(gangsa).union({"gangsa"})
    return tags


def _has_kempli_beat(gongan: Gongan) -> bool:
    """Determines if the gongan has a kempli beat.
    Args:
        gongan (Gongan):
    Returns:
        bool: True if there is a kempli beat, otherwise False
    """
    return not any(
        (meta.data.metatype == "KEMPLI" and meta.data.status is MetaDataSwitch.OFF)
        or (meta.data.metatype == "GONGAN" and meta.data.type is not GonganType.REGULAR)
        for meta in gongan.metadata
    )
