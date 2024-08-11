import csv
from copy import copy
from os import path

import pandas as pd

from src.notation_classes import Character, InstrumentTag, MidiNote, Score, System
from src.notation_constants import (
    Duration,
    InstrumentGroup,
    InstrumentPosition,
    MidiVersion,
    SymbolValue,
)
from src.settings import (
    MIDI_NOTES_DEF_FILE,
    NOTATIONFONT_DEF_FILE,
    TAGS_DEF_FILE,
    InstrumentFields,
    MidiNotesFields,
)

SYMBOL_TO_CHARACTER_LOOKUP: dict[str, Character] = dict()
SYMBOLVALUE_TO_CHARACTER_LOOKUP: dict[(SymbolValue, Duration, Duration):Character] = dict()
SYMBOLVALUE_TO_MIDINOTE_LOOKUP: dict[tuple[InstrumentPosition, SymbolValue], MidiNote] = dict()
TAG_TO_POSITION_LOOKUP: dict[InstrumentTag, InstrumentPosition] = dict()


def initialize_constants(instrumentgroup: InstrumentGroup, version: MidiVersion) -> None:
    """Initializes lookup dicts and other constants

    Args:
        instrumentgroup (InstrumentGroup): The type of orchestra (e.g. gong kebyar, semar pagulingan)
        version (Version):  Used to define which midi mapping to use from the midinotes.csv file.

    """
    global SYMBOL_TO_CHARACTER_LOOKUP, SYMBOLVALUE_TO_CHARACTER_LOOKUP, SYMBOLVALUE_TO_MIDINOTE_LOOKUP, TAG_TO_POSITION_LOOKUP
    SYMBOL_TO_CHARACTER_LOOKUP.update(create_symbol_to_character_lookup())
    SYMBOLVALUE_TO_CHARACTER_LOOKUP.update(
        {(char.value, char.duration, char.rest_after): char for char in SYMBOL_TO_CHARACTER_LOOKUP.values()}
    )
    SYMBOLVALUE_TO_MIDINOTE_LOOKUP.update(create_symbolvalue_to_midinote_lookup(instrumentgroup, version))
    TAG_TO_POSITION_LOOKUP.update(create_tag_to_position_lookup())
    x = 1


def is_silent(system: System, position: InstrumentPosition):
    no_occurrence = sum((beat.staves.get(position, []) for beat in system.beats), []) == []
    all_rests = all(char.value.isrest for beat in system.beats for char in beat.staves.get(position, []))
    return no_occurrence or all_rests


def stave_to_string(stave: list[Character]) -> str:
    return "".join((n.symbol for n in stave))


def create_rest_stave(resttype: SymbolValue, duration: float) -> list[Character]:
    """Creates a stave with rests of the given type for the given duration.
    If the duration is non-integer, the stave will also contain half and/or quarter rests.

    Args:
        resttype (SymbolValue): the type of rest (SILENCE or EXTENSION)
        duration (float): the duration, which can be non-integer.

    Returns:
        list[Character]: _description_
    """
    rest_count = int(duration)
    half_rest_count = int((duration - rest_count) * 2)
    quarter_rest_count = int((duration - rest_count - 0.5 * half_rest_count) * 4)
    rests = (
        [copy(SYMBOLVALUE_TO_CHARACTER_LOOKUP[resttype, 1, 0])] * rest_count
        + [SYMBOLVALUE_TO_CHARACTER_LOOKUP[resttype, 0.5, 0]] * half_rest_count
        + [SYMBOLVALUE_TO_CHARACTER_LOOKUP[resttype, 0.25, 0]] * quarter_rest_count
    )
    return rests


def system_to_records(system: System, skipemptylines: bool = True) -> list[dict[InstrumentPosition | int, list[str]]]:

    skip = []
    alias = dict()
    for p_pos, k_pos in [
        (InstrumentPosition.PEMADE_POLOS, InstrumentPosition.KANTILAN_POLOS),
        (InstrumentPosition.PEMADE_SANGSIH, InstrumentPosition.KANTILAN_SANGSIH),
    ]:
        if (
            p_pos in system.beats[0].staves
            and k_pos in system.beats[0].staves
            and all(beat.staves[p_pos] == beat.staves[k_pos] for beat in system.beats)
        ):
            skip.append(k_pos)
            alias[p_pos] = "GANGSA_" + p_pos.value.split("_")[1]

    result = (
        [
            {InstrumentFields.POSITION: "metadata", 1: metadata.data.model_dump_json(exclude_defaults=True)}
            for metadata in system.metadata
        ]
        + [
            {InstrumentFields.POSITION: alias.get(position, position)}
            | {beat.id: stave_to_string(beat.staves[position]) for beat in system.beats}
            for position in InstrumentPosition
            if position not in skip
            if any(position in beat.staves for beat in system.beats) and not is_silent(system, position)
        ]
        + [{InstrumentFields.POSITION: ""} | {beat.id: "" for beat in system.beats}]
    )

    return result


def score_to_notation_file(score: Score) -> None:
    score_dict = sum((system_to_records(system) for system in score.systems), [])
    score_df = pd.DataFrame.from_records(score_dict)
    filepath = path.join(
        score.source.datapath,
        score.source.outfilefmt.format(position="_CORRECTED", version="", ext="csv"),
    )
    score_df.to_csv(filepath, sep="\t", index=False, header=False, quoting=csv.QUOTE_NONE)


# Create lookup dicts based on the settings files (CSV)
#


def create_symbol_to_character_lookup(fromfile: str = NOTATIONFONT_DEF_FILE) -> dict[str, Character]:
    balifont_obj = pd.read_csv(fromfile, sep="\t", quoting=csv.QUOTE_NONE).to_dict(orient="records")
    balifont = [Character.model_validate(character) for character in balifont_obj]
    return {character.symbol: character for character in balifont}


def create_midinote_list(
    instrumentgroup: InstrumentGroup, version: MidiVersion = None, fromfile: str = MIDI_NOTES_DEF_FILE
) -> list[MidiNote]:
    midinotes_df = pd.read_csv(fromfile, sep="\t", comment="#")
    # Convert pre-filled positions to a list of InstrumentPosition values.
    # Fill in empty position fields with all positions for the instrument type.
    mask = midinotes_df[MidiNotesFields.POSITIONS].isnull()
    midinotes_df.loc[mask, MidiNotesFields.POSITIONS] = midinotes_df.loc[mask, MidiNotesFields.INSTRUMENTTYPE].apply(
        lambda x: [p for p in InstrumentPosition if p.instrumenttype == x]
    )
    # Select the required midi value
    if version:
        midinotes_df[MidiNotesFields.MIDI] = midinotes_df[version].values.tolist()
        midinotes_df.drop(list(MidiVersion), axis="columns", errors="ignore", inplace=True)
    else:
        midinotes_df[MidiNotesFields.MIDI] = -1
    # Drop unrequired instrument groups and convert to dict
    midinotes_dict = midinotes_df[midinotes_df[MidiNotesFields.INSTRUMENTGROUP] == instrumentgroup.value].to_dict(
        orient="records"
    )
    # Convert to MidiNote objects
    return [MidiNote.model_validate(note) for note in midinotes_dict]


def create_symbolvalue_to_midinote_lookup(
    instrumentgroup: InstrumentGroup, version: MidiVersion = None, fromfile: str = MIDI_NOTES_DEF_FILE
) -> dict[tuple[InstrumentPosition, SymbolValue], int]:
    midinotes = create_midinote_list(instrumentgroup, version=version, fromfile=fromfile)
    return {(note.instrumenttype, note.notevalue): note for note in midinotes}


def create_instrumentrange_lookup(instrumentgroup: InstrumentGroup, fromfile: str = MIDI_NOTES_DEF_FILE):
    midinotes = create_midinote_list(instrumentgroup, fromfile=fromfile)
    instrumenttypes = {note.instrumenttype for note in midinotes}
    return {
        instr_type: [note.notevalue for note in midinotes if note.instrumenttype == instr_type]
        for instr_type in instrumenttypes
    }


def create_tag_to_position_lookup(fromfile: str = TAGS_DEF_FILE):
    tags_dict = pd.read_csv(fromfile, sep="\t").to_dict(orient="records")
    tags = [InstrumentTag.model_validate(record) for record in tags_dict]
    return {t.tag: t.positions for t in tags}


if __name__ == "__main__":
    print(create_instrumentrange_lookup(InstrumentGroup.GONG_KEBYAR))
