import csv
from os import path

import pandas as pd

from src.common.classes import Gongan, Note, Score
from src.common.constants import NotationFont, ParserTag, Pitch, Position
from src.settings.constants import InstrumentFields


def notelist_to_string(notelist: list[Note]) -> str:  # here: gongan_to_records, test_utils
    return "".join((n.symbol for n in notelist))


def is_silent(gongan: Gongan, position: Position):  # here: gongan_to_records
    no_occurrence = sum((beat.get_notes(position, none=[]) for beat in gongan.beats), []) == []
    all_rests = all(note.pitch == Pitch.NONE for beat in gongan.beats for note in beat.get_notes(position, none=[]))
    return no_occurrence or all_rests


def gongan_to_records(gongan: Gongan, skipemptylines: bool = True) -> list[dict[Position | int, list[str]]]:
    """Converts a gongan to a dict containing the notation for the individual beats.

    Args:
        gongan (Gongan): gongan to convert
        skipemptylines (bool, optional): if true, positions without content (only rests) are skipped. Defaults to True.

    Returns:
        list[dict[Position | int, list[str]]]: _description_
    """

    # pos_tags maps positions to tag values. It contains only the positions that occur in the gongan. KEMPLI is omitted.
    pos_tags = {
        position: position.shortcode for position in gongan.beats[0].measures.keys() if position != Position.KEMPLI
    }

    def same(notes1: list[Note], notes2: list[Note]) -> bool:
        return all(
            note1.pitch == note2.pitch
            and note1.octave == note2.octave
            and note1.stroke == note2.stroke
            and note1.duration == note2.duration
            and note1.rest_after == note2.rest_after
            and note1.velocity == note2.velocity
            for note1, note2 in zip(notes1, notes2)
        )

    def try_to_aggregate(positions: list[Position], aggregate_tag: str):
        """Determines if the notation is identical for all of the given positions.
        In that case, updates the pos_tags dict.
        """
        # Check if all positions occur in the gongan
        if not all(pos in gongan.beats[0].measures for pos in positions):
            return False
        all_positions_have_same_notation = all(
            all(same(beat.get_notes(pos), beat.get_notes(positions[0])) for beat in gongan.beats) for pos in positions
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
    GANGSA_P = [Position.PEMADE_POLOS, Position.KANTILAN_POLOS]
    GANGSA_S = [Position.PEMADE_SANGSIH, Position.KANTILAN_SANGSIH]
    GANGSA = GANGSA_P + GANGSA_S
    REYONG_13 = [Position.REYONG_1, Position.REYONG_3]
    REYONG_24 = [Position.REYONG_2, Position.REYONG_4]
    REYONG = REYONG_13 + REYONG_24
    if not try_to_aggregate(GANGSA, "GANGSA"):
        try_to_aggregate(GANGSA_P, "GANGSA_P")
        try_to_aggregate(GANGSA_S, "GANGSA_S")
    if not try_to_aggregate(REYONG, "REYONG"):
        try_to_aggregate(REYONG_13, "REYONG_13")
        try_to_aggregate(REYONG_24, "REYONG_24")

    result = (
        [{InstrumentFields.POSITION: ParserTag.COMMENTS, 1: comment} for comment in gongan.comments]
        + [
            {InstrumentFields.POSITION: ParserTag.METADATA, 1: metadata.data.model_dump_notation()}
            for metadata in gongan.metadata
        ]
        + [
            {InstrumentFields.POSITION: pos_tags.get(position, position)}
            | {beat.id: notelist_to_string(beat.get_notes(position)) for beat in gongan.beats}
            for position in pos_tags.keys()
            if any(position in beat.measures for beat in gongan.beats)
            and not (is_silent(gongan, position) and skipemptylines)
        ]
        + [{InstrumentFields.POSITION: ""} | {beat.id: "" for beat in gongan.beats}]
    )

    return result


def score_to_notation_file(score: Score) -> None:  # score_validation
    """Converts a score object to notation and saves it to file.
        This method is used to export a corrected version of the original score.

    Args:
        score (Score): The score
    """
    score_dict = sum((gongan_to_records(gongan, score.settings.font.fontversion) for gongan in score.gongans), [])
    score_df = pd.DataFrame.from_records(score_dict)
    fpath, ext = path.splitext(score.settings.notation.notation_filepath)
    filepath = fpath + "_CORRECTED" + ext
    score_df.to_csv(filepath, sep="\t", index=False, header=False, quoting=csv.QUOTE_NONE)
