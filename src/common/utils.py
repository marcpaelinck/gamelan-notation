import csv
from itertools import product
from os import path
from statistics import mode

import pandas as pd

from src.common.classes import Beat, Gongan, Note, Score
from src.common.constants import (
    InstrumentPosition,
    NotationFont,
    Octave,
    Pitch,
    SpecialTags,
    Stroke,
)
from src.common.lookups import LOOKUP
from src.common.metadata_classes import GonganType, KempliMeta, MetaDataSwitch
from src.settings.settings import InstrumentFields, get_run_settings


def has_kempli_beat(gongan: Gongan):
    return (
        not (kempli := gongan.get_metadata(KempliMeta)) or kempli.status != MetaDataSwitch.OFF
    ) and gongan.gongantype not in [GonganType.KEBYAR, GonganType.GINEMAN]


def most_occurring_beat_duration(beats: list[Beat]):
    return mode(beat.duration for beat in beats)


def most_occurring_stave_duration(staves: dict[InstrumentPosition, list[Note]]):
    return mode(sum(note.total_duration for note in notes) for notes in list(staves.values()))


def is_silent(gongan: Gongan, position: InstrumentPosition):
    no_occurrence = sum((beat.staves.get(position, []) for beat in gongan.beats), []) == []
    all_rests = all(note.pitch == Pitch.NONE for beat in gongan.beats for note in beat.staves.get(position, []))
    return no_occurrence or all_rests


def stave_to_string(stave: list[Note]) -> str:
    return "".join((n.symbol for n in stave))


def find_note(pitch: Pitch, stroke: Stroke, duration: float, note_list: list[Note]) -> Note:
    return next(
        (
            note
            for note in note_list
            if (not pitch or note.pitch == pitch)
            and (not stroke or note.stroke == stroke)
            and (not duration or note.duration == duration)
        ),
        None,
    )


def get_whole_rest_note(position: InstrumentPosition, resttype: Stroke):
    return LOOKUP.POSITION_P_O_S_TO_NOTE[position][Pitch.NONE, None, resttype].get(
        (1, 0), LOOKUP.POSITION_P_O_S_TO_NOTE[position][Pitch.NONE, None, resttype].get((0, 1), None)
    )


def create_rest_stave(position: InstrumentPosition, resttype: Stroke, duration: float) -> list[Note]:
    """Creates a stave with rests of the given type for the given duration.
    If the duration is non-integer, the stave will also contain half and/or quarter rests.

    Args:
        resttype (Stroke): the type of rest (SILENCE or EXTENSION)
        duration (float): the duration, which can be non-integer.

    Returns:
        list[Note]: _description_
    """
    # TODO exception handling
    notes = []
    whole_rest: Note = get_whole_rest_note(position, resttype)
    for i in range(int(duration)):
        notes.append(whole_rest.model_copy())

    # if duration is not integer, add the fractional part as an extra rest.
    if frac_duration := duration - int(duration):
        attribute = "duration" if whole_rest.duration > 0 else "rest_after"
        notes.append(whole_rest.model_copy(update={attribute: frac_duration}))

    return notes


def gongan_to_records(
    gongan: Gongan, skipemptylines: bool = True, fontversion: NotationFont = None
) -> list[dict[InstrumentPosition | int, list[str]]]:
    # TODO grace notes that occur at the end of a beat should be moved to the start of the next beat.
    """Converts a gongan to a dict containing the notation for the individual beats.

    Args:
        gongan (Gongan): gongan to convert
        skipemptylines (bool, optional): if true, positions without content (only rests) are skipped. Defaults to True.

    Returns:
        list[dict[InstrumentPosition | int, list[str]]]: _description_
    """

    # pos_tags maps positions to tag values. It contains only the positions that occur in the gongan.
    pos_tags = {position: position.shortcode for position in gongan.beats[0].staves.keys()}

    def try_to_aggregate(positions: list[InstrumentPosition], aggregate_tag: str):
        """Determines if the notation is identical for all of the given positions.
        In that case, updates the pos_tags dict.
        """
        # Check if all positions occur in the gongan
        if not all(pos in gongan.beats[0].staves for pos in positions):
            return False
        all_positions_have_same_notation = all(
            all(beat.staves[pos] == beat.staves[positions[0]] for beat in gongan.beats) for pos in positions
        )
        if all_positions_have_same_notation:
            # Set the tag of the first position as the aggregate tag.
            pos_tags[positions[0]] = aggregate_tag
            # Delete all other positions in the pos_tags dict.
            for pos in set(positions[1:]).intersection(pos_tags.keys()):
                del pos_tags[pos]
            return True
        return False

    # Try to aggregate positions that have the same notation.
    GANGSA_P = [InstrumentPosition.PEMADE_POLOS, InstrumentPosition.KANTILAN_POLOS]
    GANGSA_S = [InstrumentPosition.PEMADE_SANGSIH, InstrumentPosition.KANTILAN_SANGSIH]
    GANGSA = GANGSA_P + GANGSA_S
    REYONG_13 = [InstrumentPosition.REYONG_1, InstrumentPosition.REYONG_3]
    REYONG_24 = [InstrumentPosition.REYONG_2, InstrumentPosition.REYONG_4]
    REYONG = REYONG_13 + REYONG_24
    if not try_to_aggregate(GANGSA, "GANGSA"):
        try_to_aggregate(GANGSA_P, "GANGSA_P")
        try_to_aggregate(GANGSA_S, "GANGSA_S")
    if not try_to_aggregate(REYONG, "REYONG"):
        try_to_aggregate(REYONG_13, "REYONG_13")
        try_to_aggregate(REYONG_24, "REYONG_24")

    # if fontversion is NotationFont.BALIMUSIC5:
    #     move_grace_notes_at_end_of_beat()

    result = (
        [{InstrumentFields.POSITION: SpecialTags.COMMENT, 1: comment} for comment in gongan.comments]
        + [
            {InstrumentFields.POSITION: SpecialTags.METADATA, 1: metadata.data.model_dump_notation()}
            for metadata in gongan.metadata
        ]
        + [
            {InstrumentFields.POSITION: pos_tags.get(position, position)}
            | {beat.id: stave_to_string(beat.staves[position]) for beat in gongan.beats}
            for position in InstrumentPosition
            if position in pos_tags.keys()
            if any(position in beat.staves for beat in gongan.beats)
            and not (is_silent(gongan, position) and skipemptylines)
        ]
        + [{InstrumentFields.POSITION: ""} | {beat.id: "" for beat in gongan.beats}]
    )

    return result


def score_to_notation_file(score: Score) -> None:
    """Converts a score object to notation and saves it to file.
        This method is used to export a corrected version of the original score.

    Args:
        score (Score): The score
    """
    score_dict = sum((gongan_to_records(gongan, score.settings.font.fontversion) for gongan in score.gongans), [])
    score_df = pd.DataFrame.from_records(score_dict)
    fpath, ext = path.splitext(score.settings.notation.filepath)
    filepath = fpath + "_CORRECTED" + ext
    score_df.to_csv(filepath, sep="\t", index=False, header=False, quoting=csv.QUOTE_NONE)


# Create lookup dicts based on the settings files (CSV)
#


def get_instrument_range(position: InstrumentPosition) -> list[tuple[Note, Octave]]:
    return {(note, oct) for (note, oct, stroke) in LOOKUP.POSITION_P_O_S_TO_NOTE[position].keys() if note and oct}


def flatten(lst: list[list | object]):
    """unpacks lists within a list in-place. lst can contain both lists and objects or scalars

    Args:
        lst (list[list  |  object]): list containing lists and objects

    Returns:
        list[object]: The list with unpacked list objects.
    """
    flattened = sum((obj if isinstance(obj, list) else [obj] for obj in lst), [])
    lst.clear()
    lst.extend(flattened)


if __name__ == "__main__":
    settings = get_run_settings()
