import math
from typing import Any

from src.common.classes import Beat, Gongan, Note, RunSettings, Score
from src.common.constants import (
    BeatId,
    Duration,
    InstrumentPosition,
    InstrumentType,
    Octave,
    Pitch,
    Stroke,
)
from src.common.logger import get_logger
from src.common.lookups import LOOKUP
from src.common.metadata_classes import GonganType, ValidationProperty
from src.common.utils import (
    create_rest_stave,
    create_rest_staves,
    get_whole_rest_note,
    has_kempli_beat,
    score_to_notation_file,
)

logger = get_logger(__name__)

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


def complement_shorthand_pokok_staves(score: Score):
    """Adds EXTENSION notes to pokok staves that only contain one note (shorthand notation)

    Args:
        score (Score):
    """
    for gongan in score.gongans:
        unequal_stave_lengths(gongan=gongan, beat_at_end=score.settings.notation.beat_at_end, autocorrect=True)


def unequal_stave_lengths(gongan: Gongan, beat_at_end: bool, autocorrect: bool) -> tuple[list[tuple[BeatId, Duration]]]:
    """Checks that the stave lengths of the individual instrument in each beat of the given gongan are all equal.

    Args:
        gongan (Gongan): the gongan to check
        autocorrect (bool): if True, an attempt will be made to correct the stave lengths of specific instruments (pokok, gongs and kempli)
                    In most scores, the notation of these instruments is simplified by omitting dashes (extensions) after each long note.
        filler (Note): Note representing the extension of the preceding note with duration 1 (a dash in the notation)

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
                corrected_positions = dict()
                for position, notes in unequal_lengths.items():
                    filler = get_whole_rest_note(position, Stroke.EXTENSION)
                    uncorrected_position = {position: sum(note.total_duration for note in notes)}
                    if position in POSITIONS_AUTOCORRECT_UNEQUAL_STAVES:
                        stave_duration = sum(note.total_duration for note in notes)
                        # Add rests of duration 1 to match the integer part of the beat's duration
                        if int(beat.duration - stave_duration) >= 1:
                            fill_content = [filler.model_copy() for count in range(int(beat.duration - len(notes)))]
                            if beat_at_end:
                                fill_content.extend(notes)
                                notes.clear()
                                notes.extend(fill_content)
                            else:
                                notes.extend(fill_content)
                            stave_duration = sum(note.total_duration for note in notes)
                        # Add an extra rest for any fractional part of the beat's duration
                        if stave_duration < beat.duration:
                            attr = "duration" if filler.stroke == Stroke.EXTENSION else "rest_after"
                            notes.append(filler.model_copy(update={attr: beat.duration - stave_duration}))
                        if sum(note.total_duration for note in notes) == beat.duration:
                            # store the original (incorrect) value
                            corrected_positions |= uncorrected_position
                if corrected_positions:
                    corrected.append({"BEAT " + beat.full_id: beat.duration} | corrected_positions)

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
    gongan: Gongan, ranges: dict[InstrumentPosition, list[(Pitch, Octave, Stroke)]], autocorrect: bool
) -> tuple[list[str, list[Note]]]:
    """Checks that the notes of each instrument matches the instrument's range.

    Args:
        gongan (Gongan): the gongan to check
        ranges(dict[InstrumentPosition, list[(Pitch, Octave, Stroke)]]): list of notes for each instrument
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
        for position, notes in beat.staves.items():
            instr_range = ranges[position]
            badnotes = list()
            for note in notes:
                if note.pitch is not Pitch.NONE and (note.pitch, note.octave, note.stroke) not in instr_range:
                    badnotes.append((note.pitch, note.octave, note.stroke))
            if badnotes:
                invalids.append({f"BEAT {beat.full_id} {position}": badnotes})
    return invalids, corrected, ignored


def get_kempyung_dict(instrumentrange: dict[tuple[Pitch, Octave], tuple[Pitch, Octave]]):
    """returns a dict mapping the kempyung note to each base note in the instrument's range.

    Args:
        instrumentrange (list[tuple[Pitch, Octave, Stroke]]): range of the instrument.

    Returns:
        dict[tuple[Pitch, Octave], tuple[Pitch, Octave]]: the kempyung dict
    """
    ordered = sorted(
        list({(note, octave) for note, octave, _ in instrumentrange if octave}),
        key=lambda item: item[0].sequence + 100 * item[1],
    )
    kempyung = zip(ordered, ordered[3:] + ordered[-3:])
    kempyung_dict = {polos: sangsih for polos, sangsih in kempyung}
    # raises error if not found (should not happen)
    return kempyung_dict


def incorrect_kempyung(
    gongan: Gongan,
    score: Score,
    ranges: dict[InstrumentPosition, list[tuple[Pitch, Octave, Stroke]]],
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
        for polos, sangsih in POSITIONS_VALIDATE_AND_CORRECT_KEMPYUNG:
            instrumentrange = ranges[polos]
            kempyung_dict = get_kempyung_dict(instrumentrange)
            # check if both instruments occur in the beat
            if all(instrument in beat.staves.keys() for instrument in (polos, sangsih)):
                # check each kempyung note
                notepairs = note_pairs(beat, (polos, sangsih))
                incorrect_detected = False
                autocorrected = False
                # only check kempyung if parts are homophone.
                if all(
                    polos.stroke == sangsih.stroke  # Unisono and playing the same stroke (muting, open or rest)
                    and polos.duration == sangsih.duration
                    and polos.rest_after == sangsih.rest_after
                    for polos, sangsih in notepairs
                ):
                    orig_sangsih_str = "".join((n.symbol for n in beat.staves[sangsih]))
                    # Check for incorrect sangsih values.
                    # When autocorrecting, run the code a second time to check for remaining errors.
                    iterations = [1, 2] if autocorrect else [1]
                    for iteration in iterations:
                        notepairs = note_pairs(beat, (polos, sangsih))
                        for seq, (polosnote, sangsihnote) in enumerate(notepairs):
                            # Check kempyung.
                            if (
                                polosnote.pitch is not Pitch.NONE
                                and sangsihnote.pitch is not Pitch.NONE
                                and not (sangsihnote.pitch, sangsihnote.octave)
                                == kempyung_dict[(polosnote.pitch, polosnote.octave)]
                            ):
                                if autocorrect and iteration == 1:
                                    correct_note, correct_octave = kempyung_dict[(polosnote.pitch, polosnote.octave)]
                                    correct_sangsih = LOOKUP.get_note(
                                        position=sangsih,
                                        pitch=correct_note,
                                        octave=correct_octave,
                                        stroke=sangsihnote.stroke,
                                        duration=sangsihnote.duration,
                                        rest_after=sangsihnote.rest_after,
                                    ).model_copy()
                                    if not (correct_sangsih):
                                        logger.error(
                                            f"Trying to create an incorrect combination {sangsih} {correct_note} OCT{correct_octave} {sangsihnote.stroke} duration={sangsihnote.duration} rest_after{sangsihnote.rest_after} while correcting kempyung."
                                        )
                                    beat.staves[sangsih][seq] = correct_sangsih
                                    autocorrected = True
                                elif iteration == iterations[-1]:
                                    # Last iterations
                                    incorrect_detected = True

                if incorrect_detected:
                    invalids.append(
                        f"BEAT {beat.full_id}: {(polos, sangsih)[0].instrumenttype} P=[{''.join((n.symbol for n in beat.staves[(polos, sangsih)[0]]))}] S=[{orig_sangsih_str}]"
                    )
                if autocorrected:
                    corrected_sangsih_str = "".join((n.symbol for n in beat.staves[(polos, sangsih)[1]]))
                    corrected.append(
                        f"BEAT {beat.full_id}: {(polos, sangsih)[0].instrumenttype} P=[{''.join((n.symbol for n in beat.staves[(polos, sangsih)[0]]))}] S=[{orig_sangsih_str}] -> [{corrected_sangsih_str}]"
                    )
    return invalids, corrected, ignored


def create_missing_staves(
    beat: Beat, prevbeat: Beat, score: Score, add_kempli: bool = True, force_silence=[]
) -> dict[InstrumentPosition, list[Note]]:
    """Returns staves for missing positions, containing rests (silence) for the duration of the given beat.
    This ensures that positions that do not occur in all the gongans will remain in sync.

    Args:
        beat (Beat): The beat that should be complemented.
        all_positions (set[InstrumentPosition]): List of all the positions that occur in the notation.

    Returns:
        dict[InstrumentPosition, list[Note]]: A dict with the generated staves.
    """

    all_instruments = (
        score.instrument_positions | {InstrumentPosition.KEMPLI} if add_kempli else score.instrument_positions
    )
    # a kempli beat is a muted stroke
    # Note: these two line are BaliMusic5 font exclusive!
    KEMPLI_BEAT = LOOKUP.get_note(
        InstrumentPosition.KEMPLI, pitch=Pitch.STRIKE, octave=None, stroke=Stroke.MUTED, duration=1, rest_after=0
    )

    if missing_positions := (all_instruments - set(beat.staves.keys())):
        staves = create_rest_staves(
            prev_beat=prevbeat, positions=missing_positions, duration=beat.duration, force_silence=force_silence
        )

        # Add a kempli beat, except if a metadata label indicates otherwise or if the kempli part was already given in the original score
        if InstrumentPosition.KEMPLI in staves.keys():  # and has_kempli_beat(gongan):
            if beat.has_kempli_beat:
                rests = create_rest_stave(InstrumentPosition.KEMPLI, Stroke.EXTENSION, beat.duration - 1)
                staves[InstrumentPosition.KEMPLI] = [KEMPLI_BEAT] + rests
            else:
                all_rests = create_rest_stave(InstrumentPosition.KEMPLI, Stroke.EXTENSION, beat.duration)
                staves[InstrumentPosition.KEMPLI] = all_rests

        return staves
    else:
        return dict()


def add_missing_staves(score: Score, add_kempli: bool = True):
    prev_beat = None
    for gongan in score.gongans:
        gongan_missing_instr = [
            pos for pos in InstrumentPosition if all(pos not in beat.staves for beat in gongan.beats)
        ]
        for beat in gongan.beats:
            # Not all positions occur in each gongan.
            # Therefore we need to add blank staves (all rests) for missing positions.
            # If an instrument is missing in the entire gongan, the last beat should consist
            # of silences (.) rather than note extensions (-). This avoids unexpected results when the next beat
            # is repeated and the kempli beat is at the end of the beat.
            force_silence = gongan_missing_instr if beat == gongan.beats[-1] else []
            missing_staves = create_missing_staves(beat, prev_beat, score, add_kempli, force_silence=force_silence)
            beat.staves.update(missing_staves)
            # Update all positions of the score
            score.instrument_positions.update({pos for pos in missing_staves})
            prev_beat = beat


def validate_score(
    score: Score,
    settings: RunSettings,
    # autocorrect: bool = False,
    # save_corrected: bool = False,
    # detailed_logging: bool = False,
) -> None:
    """Performs consistency checks and prints results.

    Args:
        score (Score): the score to analyze.
    """
    logger.info("--- SCORE VALIDATION ---")
    corrected_beat_lengths = []
    ignored_beat_lengths = []
    remaining_bad_beat_lengths = []

    corrected_stave_lengths = []
    ignored_stave_lengths = []
    remaining_bad_stave_lengths = []

    corrected_note_out_of_range = []
    ignored_note_out_of_range = []
    remaining_note_out_of_range = []

    corrected_invalid_kempyung = []
    ignored_invalid_kempyung = []
    remaining_incorrect_kempyung = []

    corrected_incorrect_norot = []
    ignored_incorrect_norot = []
    remaining_incorrect_norot = []

    corrected_incorrect_ubitan = []
    ignored_incorrect_ubitan = []
    remaining_incorrect_ubitan = []

    autocorrect = settings.options.notation_to_midi.autocorrect
    save_corrected = settings.options.notation_to_midi.save_corrected_to_file
    detailed_logging = settings.options.notation_to_midi.detailed_validation_logging

    for gongan in score.gongans:
        # Determine if the beat duration is a power of 2 (ignore kebyar)
        invalids, corrected, ignored = invalid_beat_lengths(gongan, autocorrect)
        remaining_bad_beat_lengths.extend(invalids)
        corrected_beat_lengths.extend(corrected)
        ignored_beat_lengths.extend(ignored)

        invalids, corrected, ignored = unequal_stave_lengths(
            gongan,
            beat_at_end=settings.notation.beat_at_end,
            autocorrect=autocorrect,
        )
        remaining_bad_stave_lengths.extend(invalids)
        corrected_stave_lengths.extend(corrected)
        ignored_stave_lengths.extend(ignored)

        invalids, corrected, ignored = out_of_range(gongan, ranges=score.position_range_lookup, autocorrect=autocorrect)
        remaining_note_out_of_range.extend(invalids)
        corrected_note_out_of_range.extend(corrected)
        ignored_note_out_of_range.extend(corrected)

        if score.settings.notation.autocorrect_kempyung:
            invalids, corrected, ignored = incorrect_kempyung(
                gongan, score=score, ranges=score.position_range_lookup, autocorrect=autocorrect
            )
            remaining_incorrect_kempyung.extend(invalids)
            corrected_invalid_kempyung.extend(corrected)
            ignored_invalid_kempyung.extend(ignored)

    def log_list(loglevel: callable, title: str, list: list[Any]) -> None:
        loglevel(title)
        for element in list:
            loglevel(f"    {str(element)}")

    def log_results(title: str, corrected: list[Any], ignored: list[Any], remaining: list[Any]) -> None:
        logger.info(f"{title}: corrected {len(corrected)}, ignored {len(ignored)}, remaining: {len(remaining)}")
        if detailed_logging:
            if corrected:
                log_list(logger.info, "corrected:", corrected)
            if ignored:
                log_list(logger.info, "ignored:", ignored)
        if remaining:
            log_list(logger.warning, "remaining invalids:", remaining)

    log_results("INCORRECT BEAT LENGTHS", corrected_beat_lengths, ignored_beat_lengths, remaining_bad_beat_lengths)
    log_results(
        "BEATS WITH UNEQUAL STAVE LENGTHS", corrected_stave_lengths, ignored_stave_lengths, remaining_bad_stave_lengths
    )
    log_results(
        "BEATS WITH NOTES OUT OF INSTRUMENT RANGE",
        corrected_note_out_of_range,
        ignored_note_out_of_range,
        remaining_note_out_of_range,
    )
    log_results(
        "INCORRECT KEMPYUNG", corrected_invalid_kempyung, ignored_invalid_kempyung, remaining_incorrect_kempyung
    )

    if save_corrected:
        score_to_notation_file(score)
