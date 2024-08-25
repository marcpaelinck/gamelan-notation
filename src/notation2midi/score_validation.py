import math
from pprint import pprint

from src.common.classes import Beat, Character, Gongan, Score
from src.common.constants import (
    BeatId,
    Duration,
    InstrumentPosition,
    InstrumentType,
    Note,
    Octave,
    Stroke,
)
from src.common.metadata_classes import (
    GonganType,
    KempliMeta,
    MetaDataStatus,
    ValidationProperty,
)
from src.common.utils import create_rest_stave, score_to_notation_file
from src.notation2midi.font_specific_code import get_character

POSITIONS_AUTOCORRECT_UNEQUAL_STAVES = [
    InstrumentPosition.UGAL,
    InstrumentPosition.CALUNG,
    InstrumentPosition.JEGOGAN,
    InstrumentPosition.GONGS,
    InstrumentPosition.KEMPLI,
]
POSITIONS_VALIDATE_AND_CORRECT_KEMPYUNG = [
    (InstrumentPosition.PEMADE_POLOS, InstrumentPosition.PEMADE_SANGSIH),
    (InstrumentPosition.KANTILAN_POLOS, InstrumentPosition.KANTILAN_SANGSIH),
]


def invalid_beat_lengths(gongan: Gongan, autocorrect: bool) -> tuple[list[tuple[BeatId, Duration]]]:
    """Checks the length of beats in "regular" gongans. The length should be a power of 2.

    Args:
        gongan (Gongan): the gongan to check
        autocorrect (bool): if True, an attempt will be made to correct the beat length (currently not effective)

    Returns:
        tuple[list[tuple[BeatId, Duration]]]: list of remaining invalid beats and of corrected beats.
    """
    invalids = []
    corrected = []
    ignored = []

    for beat in gongan.beats:
        if ValidationProperty.BEAT_DURATION in beat.validation_ignore:
            ignored.append(f"BEAT {beat.full_id} skipped due to override")
            continue
        if gongan.gongantype == GonganType.REGULAR and 2 ** int(math.log2(beat.duration)) != beat.duration:
            invalids.append((beat.full_id, beat.duration))
    return invalids, corrected, ignored


def unequal_stave_lengths(gongan: Gongan, autocorrect: bool, filler: Character) -> tuple[list[tuple[BeatId, Duration]]]:
    """Checks that the stave lengths of the individual instrument in each beat of the given gongan are all equal.

    Args:
        gongan (Gongan): the gongan to check
        autocorrect (bool): if True, an attempt will be made to correct the stave lengths of specific instruments (pokok, gongs and kempli)
                    In most scores, the notation of these instruments is simplified by omitting dashes (extensions) after each long note.

    Returns:
        tuple[list[tuple[BeatId, Duration]]]: list of remaining invalid beats and of corrected beats.
    """
    invalids = []
    corrected = []
    ignored = []

    for beat in gongan.beats:
        if ValidationProperty.STAVE_LENGTH in beat.validation_ignore:
            ignored.append(f"BEAT {beat.full_id} skipped due to override")
            continue
        # Check if the length of all staves in a beat are equal.
        unequal_lengths = {
            position: notes
            for position, notes in beat.staves.items()
            if sum(note.total_duration for note in notes) != beat.duration
        }
        if unequal_lengths:
            if autocorrect:
                for position, notes in unequal_lengths.items():
                    if position in POSITIONS_AUTOCORRECT_UNEQUAL_STAVES:
                        stave_duration = sum(note.total_duration for note in notes)
                        # Add rests of duration 1 to match the integer part of the beat's duration
                        if int(beat.duration - stave_duration) >= 1:
                            notes.extend([filler.model_copy() for count in range(int(beat.duration - len(notes)))])
                            stave_duration = sum(note.total_duration for note in notes)
                        # Add an extra rest for any fractional part of the beat's duration
                        if stave_duration < beat.duration:
                            attr = "duration" if filler.stroke == Stroke.EXTENSION else "rest_after"
                            notes.append(filler.model_copy(update={attr: beat.duration - stave_duration}))
                        corrected.append(
                            {"BEAT " + beat.full_id: beat.duration}
                            | {
                                pos: sum(note.total_duration for note in notes)
                                for pos, notes in unequal_lengths.items()
                            },
                        )

            unequal_lengths = {
                position: notes
                for position, notes in beat.staves.items()
                if sum(note.total_duration for note in notes) != beat.duration
            }
            if unequal_lengths:
                invalids.append(
                    {"BEAT " + beat.full_id: beat.duration}
                    | {pos: sum(note.total_duration for note in notes) for pos, notes in unequal_lengths.items()},
                )
    return invalids, corrected, ignored


def out_of_range(
    gongan: Gongan, ranges: dict[InstrumentPosition, list[(Note, Octave, Stroke)]], autocorrect: bool
) -> tuple[list[str, list[Character]]]:
    """Checks that the notes of each instrument matches the instrument's range.

    Args:
        gongan (Gongan): the gongan to check
        ranges(dict[InstrumentPosition, list[(Note, Octave, Stroke)]]): list of notes for each instrument
        autocorrect (bool): if True, an attempt will be made to correct notes that are out of range (currently not effective)

    Returns:
        tuple[list[tuple[BeatId, Duration]]]: list of remaining beats containing incorrect notes and of corrected beats.
    """
    invalids = []
    corrected = []
    ignored = []

    for beat in gongan.beats:
        if ValidationProperty.INSTRUMENT_RANGE in beat.validation_ignore:
            ignored.append(f"BEAT {beat.full_id} skipped due to override")
            continue
        for position, chars in beat.staves.items():
            instr_range = ranges[position]
            badnotes = list()
            for char in chars:
                if char.note is not Note.NONE and (char.note, char.octave, char.stroke) not in instr_range:
                    badnotes.append((char.note, char.octave, char.stroke))
            if badnotes:
                invalids.append({f"BEAT {beat.full_id} {position}": badnotes})
    return invalids, corrected, ignored


def get_kempyung_dict(instrumentrange: dict[tuple[Note, Octave], tuple[Note, Octave]]):
    """returns a dict mapping the kempyung note to each base note in the instrument's range.

    Args:
        instrumentrange (list[tuple[Note, Octave, Stroke]]): range of the instrument.

    Returns:
        dict[tuple[Note, Octave], tuple[Note, Octave]]: the kempyung dict
    """
    ordered = sorted(
        list({(note, octave) for note, octave, _ in instrumentrange}),
        key=lambda item: item[0].sequence + 100 * item[1],
    )
    kempyung = zip(ordered, ordered[3:] + ordered[-3:])
    kempyung_dict = {polos: sangsih for polos, sangsih in kempyung}
    # raises error if not found (should not happen)
    return kempyung_dict


def incorrect_kempyung(
    gongan: Gongan,
    score: Score,
    ranges: dict[InstrumentPosition, list[tuple[Note, Octave, Stroke]]],
    autocorrect: bool,
) -> list[tuple[BeatId, tuple[InstrumentPosition, InstrumentPosition]]]:
    def note_pairs(beat: Beat, pair: list[InstrumentType]):
        return list(zip([n for n in beat.staves[pair[0]]], [n for n in beat.staves[pair[1]]]))

    invalids = []
    corrected = []
    ignored = []
    for beat in gongan.beats:
        if ValidationProperty.KEMPYUNG in beat.validation_ignore:
            ignored.append(f"BEAT {beat.full_id} skipped due to override")
            continue
        for pair in POSITIONS_VALIDATE_AND_CORRECT_KEMPYUNG:
            instrumentrange = ranges[pair[0]]
            kempyung_dict = get_kempyung_dict(instrumentrange)
            # check if both instruments occur in the beat
            if all(instrument in beat.staves.keys() for instrument in pair):
                # check each kempyung note
                notepairs = note_pairs(beat, pair)
                incorrect_detected = False
                autocorrected = False
                # only check kempyung if parts are homophone.
                if all(
                    polos.stroke == sangsih.stroke  # Unisono and playing the same stroke (muting, open or rest)
                    and polos.duration == sangsih.duration
                    and polos.rest_after == sangsih.rest_after
                    for polos, sangsih in notepairs
                ):
                    orig_sangsih_str = "".join((n.symbol for n in beat.staves[pair[1]]))
                    # Check for incorrect sangsih values.
                    # When autocorrecting, run the code a second time to check for remaining errors.
                    iterations = [1, 2] if autocorrect else [1]
                    for iteration in iterations:
                        notepairs = note_pairs(beat, pair)
                        for seq, (polos, sangsih) in enumerate(notepairs):
                            # Check kempyung.
                            if (
                                polos.note is not Note.NONE
                                and sangsih.note is not Note.NONE
                                and not (sangsih.note, sangsih.octave) == kempyung_dict[(polos.note, polos.octave)]
                            ):
                                if autocorrect and iteration == 1:
                                    correct_note, correct_octave = kempyung_dict[(polos.note, polos.octave)]
                                    correct_sangsih = get_character(
                                        note=correct_note,
                                        octave=correct_octave,
                                        stroke=sangsih.stroke,
                                        duration=sangsih.duration,
                                        rest_after=sangsih.rest_after,
                                        symbol=sangsih.symbol,  # will be returned with corrected note symbol
                                        font=score.source.font,
                                    )
                                    beat.staves[pair[1]][seq] = correct_sangsih
                                    autocorrected = True
                                elif iteration == iterations[-1]:
                                    # Last iterations
                                    incorrect_detected = True

                if incorrect_detected:
                    invalids.append(
                        f"BEAT {beat.full_id}: {pair[0].instrumenttype} P=[{''.join((n.symbol for n in beat.staves[pair[0]]))}] S=[{orig_sangsih_str}]"
                    )
                if autocorrected:
                    corrected_sangsih_str = "".join((n.symbol for n in beat.staves[pair[1]]))
                    corrected.append(
                        f"BEAT {beat.full_id}: {pair[0].instrumenttype} P=[{''.join((n.symbol for n in beat.staves[pair[0]]))}] S=[{orig_sangsih_str}] -> [{corrected_sangsih_str}]"
                    )
    return invalids, corrected, ignored


def create_missing_staves(beat: Beat, prevbeat: Beat, score: Score) -> dict[InstrumentPosition, list[Character]]:
    """Returns staves for missing positions, containing rests (silence) for the duration of the given beat.
    This ensures that positions that do not occur in all the gongans will remain in sync.

    Args:
        beat (Beat): The beat that should be complemented.
        all_positions (set[InstrumentPosition]): List of all the positions that occur in the notation.

    Returns:
        dict[InstrumentPosition, list[Character]]: A dict with the generated staves.
    """

    if missing_positions := ((score.instrument_positions | {InstrumentPosition.KEMPLI}) - set(beat.staves.keys())):
        silence = Stroke.SILENCE
        extension = Stroke.EXTENSION
        prevstrokes = {pos: (prevbeat.staves[pos][-1].stroke if prevbeat else silence) for pos in missing_positions}
        resttypes = {pos: silence if prevstroke is silence else extension for pos, prevstroke in prevstrokes.items()}
        staves = {position: create_rest_stave(resttypes[position], beat.duration) for position in missing_positions}
        gongan = score.gongans[beat.sys_seq]
        # Add a kempli beat, except if a metadata label indicates otherwise or if the kempli part was already given in the original score
        if (
            InstrumentPosition.KEMPLI in staves.keys()
            and (not (kempli := gongan.get_metadata(KempliMeta)) or kempli.status != MetaDataStatus.OFF)
            and gongan.gongantype not in [GonganType.KEBYAR, GonganType.GINEMAN]
        ):
            kemplibeat = next(
                (
                    char
                    for char in score.balimusic_font_dict.values()
                    if char.note == Note.TICK and char.stroke == Stroke.OPEN and char.duration == 1
                ),
                None,
            )
            staves[InstrumentPosition.KEMPLI] = [kemplibeat] + create_rest_stave(Stroke.EXTENSION, beat.duration - 1)
        return staves
    else:
        return dict()


def add_missing_staves(score: Score):
    prev_beat = None
    for gongan in score.gongans:
        for beat in gongan.beats:
            # Not all positions occur in each gongan.
            # Therefore we need to add blank staves (all rests) for missing positions.
            missing_staves = create_missing_staves(beat, prev_beat, score)
            beat.staves.update(missing_staves)
            # Update all positions of the score
            score.instrument_positions.update({pos for pos in missing_staves})
            prev_beat = beat


def validate_score(
    score: Score,
    autocorrect: bool = False,
    save_corrected: bool = False,
    detailed_logging: bool = False,
) -> None:
    """Performs consistency checks and prints results.

    Args:
        score (Score): the score to analyze.
    """
    print("========= SCORE VALIDATION =========")
    beats_with_length_not_pow2 = []
    beats_with_unequal_stave_lengths = []
    beats_with_note_out_of_instrument_range = []
    beats_with_incorrect_kempyung = []
    beats_with_incorrect_norot = []
    beats_with_incorrect_ubitan = []
    corrected_stave_lengths = []
    corrected_invalid_kempyung = []
    count_corrected_beat_lengths = 0
    count_corrected_stave_lengths = 0
    count_corrected_notes_out_of_range = 0
    count_corrected_invalid_kempyung = 0
    count_corrected_beats_with_incorrect_norot = 0
    count_corrected_beats_with_incorrect_ubitan = 0
    count_ignored_beat_lengths = 0
    count_ignored_stave_lengths = 0
    count_ignored_notes_out_of_range = 0
    count_ignored_invalid_kempyung = 0
    count_ignored_beats_with_incorrect_norot = 0
    count_ignored_beats_with_incorrect_ubitan = 0

    filler = next(
        char
        for char in score.balimusic_font_dict.values()
        if char.stroke == Stroke.EXTENSION and char.total_duration == 1
    )

    for gongan in score.gongans:
        # Determine if the beat duration is a power of 2 (ignore kebyar)
        invalids, corrected, ignored = invalid_beat_lengths(gongan, autocorrect)
        beats_with_length_not_pow2.extend(invalids)
        count_corrected_beat_lengths += len(corrected)
        count_ignored_beat_lengths += len(ignored)

        invalids, corrected, ignored = unequal_stave_lengths(gongan, filler=filler, autocorrect=autocorrect)
        beats_with_unequal_stave_lengths.extend(invalids)
        corrected_stave_lengths.extend(corrected)
        count_corrected_stave_lengths += len(corrected)
        count_ignored_stave_lengths += len(ignored)

        invalids, corrected, ignored = out_of_range(gongan, ranges=score.position_range_lookup, autocorrect=autocorrect)
        beats_with_note_out_of_instrument_range.extend(invalids)
        count_corrected_notes_out_of_range += len(corrected)
        count_ignored_notes_out_of_range += len(ignored)

        invalids, corrected, ignored = incorrect_kempyung(
            gongan, score=score, ranges=score.position_range_lookup, autocorrect=autocorrect
        )
        beats_with_incorrect_kempyung.extend(invalids)
        corrected_invalid_kempyung.extend(corrected)
        count_corrected_invalid_kempyung += len(corrected)
        count_ignored_invalid_kempyung += len(ignored)

    print(
        f"INCORRECT BEAT LENGTHS (corrected {count_corrected_beat_lengths}, ignored {count_ignored_beat_lengths} beats):"
    )
    if count_corrected_beat_lengths > 0:
        pprint([])
    pprint(beats_with_length_not_pow2)
    print(
        f"UNEQUAL STAVE LENGTHS WITHIN BEAT (corrected {count_corrected_stave_lengths}, ignored {count_ignored_stave_lengths} beats):"
    )
    if detailed_logging:
        print("corrected:")
        pprint(corrected_stave_lengths)
    print("remaining invalids:")
    pprint(beats_with_unequal_stave_lengths)
    print(
        f"NOTES NOT IN INSTRUMENT RANGE (corrected {count_corrected_notes_out_of_range}, ignored {count_ignored_notes_out_of_range} beats):"
    )
    pprint(beats_with_note_out_of_instrument_range)
    print(
        f"INCORRECT KEMPYUNG (corrected {count_corrected_invalid_kempyung}, ignored {count_ignored_invalid_kempyung} beats):"
    )
    if detailed_logging:
        print("corrected:")
        pprint(corrected_invalid_kempyung)
    print("remaining invalids:")
    pprint(beats_with_incorrect_kempyung)
    print("====================================")

    if save_corrected:
        score_to_notation_file(score)
