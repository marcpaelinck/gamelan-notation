import math
from pprint import pprint

from src.common.classes import Beat, Character, Score, System
from src.common.constants import (
    BeatId,
    Duration,
    GonganType,
    InstrumentPosition,
    InstrumentType,
    Modifier,
    Note,
    Octave,
    Stroke,
)
from src.common.utils import CHARACTER_LIST, create_rest_stave, score_to_notation_file

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
        instrument: [(note, octave, stroke) for instr, note, octave, stroke in instrumentnotes if instr == instrument]
        for instrument in set(i for i, _, _, _ in instrumentnotes)
    }
    x = 1


def invalid_beat_lengths(system: System, autocorrect: bool) -> tuple[list[tuple[BeatId, Duration]]]:
    invalids = []
    corrected = []

    for beat in system.beats:
        if system.gongantype != GonganType.KEBYAR and 2 ** int(math.log2(beat.duration)) != beat.duration:
            invalids.append((beat.full_id, beat.duration))
    return invalids, corrected


def unequal_stave_lengths(system: System, autocorrect: bool, filler: Character) -> tuple[list[tuple[BeatId, Duration]]]:
    invalids = []
    corrected = []

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
    return invalids, corrected


def out_of_range(
    system: System, ranges: dict[InstrumentType, list[(Note, Octave, Stroke)]], autocorrect: bool
) -> tuple[list[str, list[Character]]]:
    invalids = []
    corrected = []

    for beat in system.beats:
        for position, chars in beat.staves.items():
            instr_range = ranges[position.instrumenttype]
            badnotes = list()
            for char in chars:
                if char.note is not Note.NONE and (char.note, char.octave, char.stroke) not in instr_range:
                    badnotes.append((char.note, char.octave, char.stroke))
            if badnotes:
                invalids.append({f"BEAT {beat.full_id} {position}": badnotes})
    return invalids, corrected


def get_kempyung(
    polos: Character,
    instrumentrange: list[tuple[Note, Octave, Stroke]],
):
    ordered = sorted(
        list({(note, octave) for note, octave, _ in instrumentrange}),
        key=lambda item: item[0].sequence + 10 * item[1],
    )
    kempyung = zip(ordered, ordered[3:] + ordered[-3:])
    kempyung_dict = {polos: sangsih for polos, sangsih in kempyung}
    # raises error if not found (should not happen)
    return kempyung_dict[(polos.note, polos.octave)]


def iskempyung(
    polos: Character,
    sangsih: Character,
    instrumentrange: list[tuple[Note, Octave, Stroke]],
):
    ordered = sorted(
        list({(note, octave) for note, octave, _ in instrumentrange}),
        key=lambda item: item[0].sequence + 10 * item[1],
    )
    kempyung = zip(ordered, ordered[3:] + ordered[-3:])
    return ((polos.note, polos.octave), (sangsih.note, sangsih.octave)) in kempyung


def create_character(
    note: Note,
    octave: int,
    stroke: Stroke,
    duration: float,
    rest_after: float,
    symbol: str = "",
    unicode: str = "",
    symbol_description: str = "",
    balifont_symbol_description: str = "",
    modifier: Modifier = Modifier.NONE,
    description: str = "",
) -> Character:
    return Character(
        note=note,
        octave=octave,
        stroke=stroke,
        duration=duration,
        rest_after=rest_after,
        symbol=symbol,
        unicode=unicode,
        symbol_description=symbol_description,
        balifont_symbol_description=balifont_symbol_description,
        modifier=modifier,
        description=description,
    )


def get_character(
    note: Note, octave: Octave, stroke: Stroke, duration: Duration, rest_after: Duration, symbol: str
) -> Character:
    char = next((char for char in CHARACTER_LIST if char.matches(note, octave, stroke, duration, rest_after)), None)
    char = char or next((char for char in CHARACTER_LIST if char.matches(note, octave, stroke, 1, 0)), None)
    char = char or next((char for char in CHARACTER_LIST if char.matches(note, octave, Stroke.OPEN, 1, 0)), None)
    char = char or next((char for char in CHARACTER_LIST if char.matches(note, 1, Stroke.OPEN, 1, 0)), None)
    char = char or create_character(note, octave, stroke, duration, rest_after, symbol="@")
    return char.model_copy(
        update={
            "symbol": char.symbol + symbol[1:],
            "octave": octave,
            "stroke": stroke,
            "duration": duration,
            "rest_after": rest_after,
        }
    )


def get_correct_kempyung(
    polos: Character, sangsih: Character, score: Score, instrumentrange: list[tuple[Note, Octave, Stroke]]
):
    note, octave = get_kempyung(polos, instrumentrange)
    correct_sangsih = get_character(
        note=note,
        octave=octave,
        stroke=sangsih.stroke,
        duration=sangsih.duration,
        rest_after=sangsih.rest_after,
        symbol=sangsih.symbol,
    )
    return correct_sangsih


def incorrect_kempyung(
    system: System,
    score: Score,
    ranges: dict[InstrumentType, list[tuple[Note, Octave, Stroke]]],
    autocorrect: bool,
) -> list[tuple[BeatId, tuple[InstrumentPosition, InstrumentPosition]]]:
    def note_pairs(beat: Beat, pair: list[InstrumentType]):
        return list(zip([n for n in beat.staves[pair[0]]], [n for n in beat.staves[pair[1]]]))

    invalids = []
    corrected = []
    for beat in system.beats:
        for pair in POSITIONS_VALIDATE_AND_CORRECT_KEMPYUNG:
            instrumentrange = ranges[pair[0].instrumenttype]
            # check if both instruments occur in the beat
            if all(instrument in beat.staves.keys() for instrument in pair):
                # check each kempyung note
                notepairs = note_pairs(beat, pair)
                # only check kempyung if parts are homophone.
                incorrect_detected = False
                autocorrected = False
                if all(
                    polos.stroke == sangsih.stroke  # Unisono and playing the same stroke (muting, open or rest)
                    and polos.duration == sangsih.duration
                    and polos.rest_after == sangsih.rest_after
                    for polos, sangsih in notepairs
                ):
                    orig_sangsih_str = "".join((n.symbol for n in beat.staves[pair[1]]))
                    # Check for incorrect sangsih values.
                    # When autocorrecting, run the code a second time to check corrections.
                    iterations = [1, 2] if autocorrect else [1]
                    for iteration in iterations:
                        notepairs = note_pairs(beat, pair)
                        for seq, (polos, sangsih) in enumerate(notepairs):
                            # Kempyung is only valid if muting status of both notes is the same.
                            if (
                                polos.note is not Note.NONE
                                and sangsih.note is not Note.NONE
                                and not iskempyung(polos, sangsih, instrumentrange=instrumentrange)
                            ):
                                if autocorrect and iteration == 1:
                                    correct_sangsih = get_correct_kempyung(
                                        polos=polos, sangsih=sangsih, score=score, instrumentrange=instrumentrange
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
    return invalids, corrected


def create_missing_staves(beat: Beat, prevbeat: Beat, score: Score) -> dict[InstrumentPosition, list[Character]]:
    """Returns staves for missing positions, containing rests (silence) for the duration of the given beat.
    This ensures that positions that do not occur in all the systems will remain in sync.

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
        # Add a kempli beat, except in case of kebyar of if the kempli part was already given in the original score
        if (
            InstrumentPosition.KEMPLI in staves.keys()
            and score.systems[beat.sys_seq].gongantype is not GonganType.KEBYAR
        ):
            kemplibeat = next(
                (
                    char
                    for char in score.balimusic_font_dict.values()
                    if char.note == Note.TICK and char.stroke == Stroke.ONE_PANGGUL and char.duration == 1
                ),
                None,
            )
            staves[InstrumentPosition.KEMPLI] = [kemplibeat] + create_rest_stave(Stroke.EXTENSION, beat.duration - 1)
        return staves
    else:
        return dict()


def add_missing_staves(score: Score):
    prev_beat = None
    for system in score.systems:
        for beat in system.beats:
            # Not all positions occur in each system.
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
    extensive_logging: bool = False,
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

    initialize_lookups(score)

    filler = next(
        char
        for char in score.balimusic_font_dict.values()
        if char.stroke == Stroke.EXTENSION and char.total_duration == 1
    )

    for system in score.systems:
        # Determine if the beat duration is a power of 2 (ignore kebyar)
        invalids, corrected = invalid_beat_lengths(system, autocorrect)
        beats_with_length_not_pow2.extend(invalids)
        count_corrected_beat_lengths += len(corrected)

        invalids, corrected = unequal_stave_lengths(system, filler=filler, autocorrect=autocorrect)
        beats_with_unequal_stave_lengths.extend(invalids)
        corrected_stave_lengths.extend(corrected)
        count_corrected_stave_lengths += len(corrected)

        invalids, corrected = out_of_range(system, ranges=INSTRUMENT_TO_RANGE_LOOKUP, autocorrect=autocorrect)
        beats_with_note_out_of_instrument_range.extend(invalids)
        count_corrected_notes_out_of_range += len(corrected)

        invalids, corrected = incorrect_kempyung(
            system, score=score, ranges=INSTRUMENT_TO_RANGE_LOOKUP, autocorrect=autocorrect
        )
        beats_with_incorrect_kempyung.extend(invalids)
        corrected_invalid_kempyung.extend(corrected)
        count_corrected_invalid_kempyung += len(corrected)

    print(f"INCORRECT BEAT LENGTHS (corrected {count_corrected_beat_lengths}):")
    if count_corrected_beat_lengths > 0:
        pprint([])
    pprint(beats_with_length_not_pow2)
    print(f"UNEQUAL STAVE LENGTHS WITHIN BEAT (corrected {count_corrected_stave_lengths}):")
    if extensive_logging:
        print("corrected:")
        pprint(corrected_stave_lengths)
    print("remaining invalids:")
    pprint(beats_with_unequal_stave_lengths)
    print(f"NOTES NOT IN INSTRUMENT RANGE (corrected {count_corrected_notes_out_of_range}):")
    pprint(beats_with_note_out_of_instrument_range)
    print(f"INCORRECT KEMPYUNG (corrected {count_corrected_invalid_kempyung}):")
    if extensive_logging:
        print("corrected:")
        pprint(corrected_invalid_kempyung)
    print("remaining invalids:")
    pprint(beats_with_incorrect_kempyung)
    print("====================================")

    if save_corrected:
        score_to_notation_file(score)


if __name__ == "__main__":
    pass
