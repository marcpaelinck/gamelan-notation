import math
from pprint import pprint

from src.notation_classes import Beat, Character, Score, System
from src.notation_constants import InstrumentPosition, InstrumentType, Note, SymbolValue
from src.utils import score_to_notation_file

Duration = int
BeatId = str

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

INSTRUMENT_TO_RANGE_LOOKUP = None


def initialize_lookups(score: Score):
    global INSTRUMENT_TO_RANGE_LOOKUP
    instrumentnotes = list(score.midi_notes_dict.keys())
    INSTRUMENT_TO_RANGE_LOOKUP = {
        instrument: [note for instr, note in instrumentnotes if instr == instrument]
        for instrument in set(i for i, _ in instrumentnotes)
    }


def invalid_beat_lengths(system: System, autocorrect: bool) -> list[tuple[BeatId, Duration]]:
    invalids = []
    corrected_count = 0

    for beat in system.beats:
        if system.gongan.kind != "kebyar" and 2 ** int(math.log2(beat.duration)) != beat.duration:
            invalids.append((beat.full_id, beat.duration))
    return invalids, corrected_count


def unequal_stave_lengths(system: System, autocorrect: bool, filler: Character) -> list[tuple[BeatId, Duration]]:
    invalids = []
    corrected_count = 0

    for beat in system.beats:
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
                        if len(notes) == 1:
                            notes.extend([filler.model_copy() for count in range(int(beat.duration - len(notes)))])
                corrected_count += 1
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
    return invalids, corrected_count


def out_of_range(system: System, ranges: dict[InstrumentType, list[SymbolValue]], autocorrect: bool):
    invalids = list()
    corrected_count = 0

    for beat in system.beats:
        for position, notes in beat.staves.items():
            instr_range = ranges[position.instrumenttype]
            badnotes = list()
            for note in notes:
                if note.value.isnote and note.value not in instr_range:
                    badnotes.append(note.value.value)
            if badnotes:
                invalids.append({f"BEAT {beat.full_id} {position}": badnotes})
    return invalids, corrected_count


def get_kempyung(
    polos: SymbolValue,
    instrumentrange: list[SymbolValue],
):
    ordered = sorted(list({(s.note, s.octave) for s in instrumentrange}), key=lambda v: v[0].sequence + 10 * v[1])
    kempyung = zip(ordered, ordered[3:] + ordered[-3:])
    kempyung_dict = {polos: sangsih for polos, sangsih in kempyung}
    # raises error if not found (should not happen)
    return kempyung_dict[(polos.note, polos.octave)]


def iskempyung(
    polos: SymbolValue,
    sangsih: SymbolValue,
    instrumentrange: list[SymbolValue],
):
    ordered = sorted(list({(s.note, s.octave) for s in instrumentrange}), key=lambda v: v[0].sequence + 10 * v[1])
    kempyung = zip(ordered, ordered[3:] + ordered[-3:])
    return ((polos.note, polos.octave), (sangsih.note, sangsih.octave)) in kempyung


def find_character(note: Note, octave: int, duration: float, rest_after: float, charlist: list[Character]):
    return next(
        (
            ch
            for ch in charlist
            if ch.value.note == note
            and ch.value.octave == octave
            and ch.duration == duration
            and ch.rest_after == rest_after
        ),
        None,
    )


def get_correct_kempyung(polos: Character, sangsih: Character, score: Score, instrumentrange: list[SymbolValue]):
    note, octave = get_kempyung(polos.value, instrumentrange)
    correct_sangsih = find_character(
        note,
        octave,
        sangsih.duration,
        sangsih.rest_after,
        score.balimusic4_font_dict.values(),
    )
    if not correct_sangsih:
        # Note duration was modified
        correct_sangsih = find_character(
            note,
            octave,
            1,
            0,
            score.balimusic4_font_dict.values(),
        ).model_copy(update={"duration": sangsih.duration, "rest_after": sangsih.rest_after})
    else:
        correct_sangsih = correct_sangsih.model_copy()
    return correct_sangsih


def incorrect_kempyung(
    system: System,
    score: Score,
    ranges: dict[InstrumentType, list[SymbolValue]],
    autocorrect: bool,
) -> list[tuple[BeatId, tuple[InstrumentPosition, InstrumentPosition]]]:
    def note_pairs(beat: Beat, pair: list[InstrumentType]):
        return list(zip([n for n in beat.staves[pair[0]]], [n for n in beat.staves[pair[1]]]))

    invalids = []
    corrected_counter = 0
    for beat in system.beats:
        for pair in POSITIONS_VALIDATE_AND_CORRECT_KEMPYUNG:
            instrumentrange = ranges[pair[0].instrumenttype]
            # check if both instruments occur in the beat
            if all(instrument in beat.staves.keys() for instrument in pair):
                # check each kempyung note
                notepairs = note_pairs(beat, pair)
                # only check kempyung if parts are homophone.
                incorrect_detected = False
                if all(
                    polos.value.isnote == sangsih.value.isnote
                    and polos.value.isrest == sangsih.value.isrest
                    and polos.duration == sangsih.duration
                    and polos.rest_after == sangsih.rest_after
                    for polos, sangsih in notepairs
                ):
                    # Check for incorrect sangsih values.
                    # When autocorrecting, run the code a second time to check corrections.
                    iterations = [1, 2] if autocorrect else [1]
                    for iteration in iterations:
                        notepairs = note_pairs(beat, pair)
                        for seq, (polos, sangsih) in enumerate(notepairs):
                            # Kempyung is only valid if muting status of both notes is the same.
                            if (
                                polos.value.isnote
                                and sangsih.value.isnote
                                and polos.value.mutingtype == sangsih.value.mutingtype
                                and not iskempyung(polos.value, sangsih.value, instrumentrange=instrumentrange)
                            ):
                                if autocorrect and iteration == 1:
                                    correct_sangsih = get_correct_kempyung(
                                        polos=polos, sangsih=sangsih, score=score, instrumentrange=instrumentrange
                                    )
                                    notes = beat.staves[pair[1]]
                                    beat.staves[pair[1]][seq] = correct_sangsih
                                    # print(
                                    #     f"beat {beat.full_id} {pair[0].instrumenttype}: polos {polos.value} replaced sangsih {sangsih.value} with {correct_sangsih.value}"
                                    # )
                                    corrected_counter += 1
                                elif iteration == iterations[-1]:
                                    # Last iterations
                                    incorrect_detected = True

                if incorrect_detected:
                    invalids.append(
                        f"BEAT {beat.full_id}: {pair[0].instrumenttype} P=[{''.join((n.symbol for n in beat.staves[pair[0]]))}] S=[{''.join((n.symbol for n in beat.staves[pair[1]]))}]"
                    )
    return invalids, corrected_counter


def validate_score(
    score: Score,
    autocorrect: bool = False,
    save_corrected: bool = False,
) -> None:
    """Performs consistency checks and prints results.

    Args:
        score (Score): the score to analyze.
    """
    beats_with_length_not_pow2 = []
    beats_with_unequal_stave_lengths = []
    beats_with_note_out_of_instrument_range = []
    beats_with_incorrect_kempyung = []
    beats_with_incorrect_norot = []
    beats_with_incorrect_ubitan = []
    count_corrected_beat_lengths = 0
    count_corrected_stave_lengths = 0
    count_corrected_notes_out_of_range = 0
    count_corrected_invalid_kempyung = 0
    count_beats_with_incorrect_norot = 0
    count_beats_with_incorrect_ubitan = 0

    initialize_lookups(score)

    filler = next(
        char
        for char in score.balimusic4_font_dict.values()
        if char.value == SymbolValue.EXTENSION and char.total_duration == 1
    )

    for system in score.systems:
        # Determine if the beat duration is a power of 2 (ignore kebyar)
        invalids, count = invalid_beat_lengths(system, autocorrect)
        beats_with_length_not_pow2.extend(invalids)
        count_corrected_beat_lengths += count

        invalids, count = unequal_stave_lengths(system, filler=filler, autocorrect=autocorrect)
        beats_with_unequal_stave_lengths.extend(invalids)
        count_corrected_stave_lengths += count

        invalids, count = out_of_range(system, ranges=INSTRUMENT_TO_RANGE_LOOKUP, autocorrect=autocorrect)
        beats_with_note_out_of_instrument_range.extend(invalids)
        count_corrected_notes_out_of_range += count

        invalids, count = incorrect_kempyung(
            system, score=score, ranges=INSTRUMENT_TO_RANGE_LOOKUP, autocorrect=autocorrect
        )
        beats_with_incorrect_kempyung.extend(invalids)
        count_corrected_invalid_kempyung += count

    print(f"INCORRECT BEAT LENGTHS (corrected {count_corrected_beat_lengths}):")
    pprint(beats_with_length_not_pow2)
    print(f"UNEQUAL STAVE LENGTHS WITHIN BEAT (corrected {count_corrected_stave_lengths}):")
    pprint(beats_with_unequal_stave_lengths)
    print(f"NOTES NOT IN INSTRUMENT RANGE (corrected {count_corrected_notes_out_of_range}):")
    pprint(beats_with_note_out_of_instrument_range)
    print(f"INCORRECT KEMPYUNG (corrected {count_corrected_invalid_kempyung}):")
    pprint(beats_with_incorrect_kempyung)

    if save_corrected:
        score_to_notation_file(score)


if __name__ == "__main__":
    pass
