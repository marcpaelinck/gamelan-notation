import math

from notation_classes import Score, System
from notation_constants import InstrumentGroup, InstrumentPosition

Duration = int
BeatId = str


def invalid_beat_lengths(system: System) -> list[tuple[BeatId, Duration]]:
    invalids = []
    for beat in system.beats:
        if system.gongan.kind != "kebyar" and 2 ** int(math.log2(beat.duration)) != beat.duration:
            invalids.append((beat.full_id, beat.duration))
    return invalids


def unequal_stave_lengths(system: System) -> list[tuple[BeatId, Duration]]:
    invalids = []
    for beat in system.beats:
        # Check if the length of all staves in a beat are equal.
        if any(sum(note.total_duration for note in notes) != beat.duration for notes in beat.staves.values()):
            invalids.append(
                {"BEAT " + beat.full_id: beat.duration}
                | {
                    pos: sum(note.total_duration for note in notes)
                    for pos, notes in beat.staves.items()
                    if sum(note.total_duration for note in notes) != beat.duration
                },
            )
    return invalids


def incorrect_kempyung(
    system: System, group: InstrumentGroup
) -> list[tuple[BeatId, tuple[InstrumentPosition, InstrumentPosition]]]:
    invalids = []
    for beat in system.beats:
        for pair in [
            (InstrumentPosition.PEMADE_POLOS, InstrumentPosition.PEMADE_SANGSIH),
            (InstrumentPosition.KANTILAN_POLOS, InstrumentPosition.KANTILAN_SANGSIH),
        ]:
            if all(instrument in beat.staves.keys() for instrument in pair):
                # check each kempyiung note
                notepairs = list(
                    zip([n.meaning for n in beat.staves[pair[0]]], [n.meaning for n in beat.staves[pair[1]]])
                )
                # only kempyung check if homophone parts
                if all(
                    polos.isnote == sangsih.isnote and polos.isrest == sangsih.isrest for polos, sangsih in notepairs
                ):
                    if not all(
                        polos.isrest or sangsih.iskempyungof(polos, instrumentgroup=group)
                        for polos, sangsih in notepairs
                    ):
                        invalids.append({"BEAT " + beat.full_id: pair})
    return invalids


def validate_score(score: Score, instrumentgroup: InstrumentGroup) -> None:
    """Performs consistency checks and prints results.

    Args:
        score (Score): the score to analyze.
    """
    beat_not_pow2 = []
    beat_unequal_stave_lengths = []
    out_of_instrument_range = []
    beats_with_incorrect_kempyung = []
    incorrect_norot = []
    incorrect_ubitan = []

    for system in score.systems:
        # Determine if the beat duration is a power of 2 (ignore kebyar)
        beat_not_pow2.extend(invalid_beat_lengths(system))
        beat_unequal_stave_lengths.extend(unequal_stave_lengths(system))
        beats_with_incorrect_kempyung.extend(incorrect_kempyung(system, instrumentgroup))
    print(f"INCORRECT LENGTHS: {beat_not_pow2}")
    print(f"UNEQUAL LENGTHS: {beat_unequal_stave_lengths}")
    print(f"INCORRECT KEMPYUNG: {beats_with_incorrect_kempyung}")
