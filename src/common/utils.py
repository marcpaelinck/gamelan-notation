import csv
from os import path

import numpy as np
import pandas as pd

from src.common.classes import Gongan, MidiNote, Note, Score, Source
from src.common.constants import (
    InstrumentGroup,
    InstrumentPosition,
    MIDIvalue,
    MidiVersion,
    Octave,
    Pitch,
    Stroke,
)
from src.common.lookups import (
    NOTE_LIST,
    POSITION_TO_RANGE_LOOKUP,
    SYMBOL_TO_NOTE_LOOKUP,
    SYMBOLVALUE_TO_MIDINOTE_LOOKUP,
    TAG_TO_POSITION_LOOKUP,
    InstrumentTag,
)
from src.common.metadata_classes import SilenceMeta
from src.notation2midi.settings import (
    COMMENT,
    METADATA,
    MIDI_NOTES_DEF_FILE,
    NOTATIONFONT_DEF_FILES,
    TAGS_DEF_FILE,
    InstrumentFields,
    MidiNotesFields,
)


def read_settings(source: Source, version: MidiVersion, midi_notes_file: str) -> None:
    """Initializes lookup dicts and lists from settings files

    Args:
        instrumentgroup (InstrumentGroup): The type of orchestra (e.g. gong kebyar, semar pagulingan)
        version (Version):  Used to define which midi mapping to use from the midinotes.csv file.

    """
    # global SYMBOL_TO_NOTE_LOOKUP, NOTE_LIST, SYMBOLVALUE_TO_MIDINOTE_LOOKUP
    SYMBOL_TO_NOTE_LOOKUP.update(create_symbol_to_note_lookup(NOTATIONFONT_DEF_FILES[source.font]))
    NOTE_LIST.extend(list(SYMBOL_TO_NOTE_LOOKUP.values()))
    SYMBOLVALUE_TO_MIDINOTE_LOOKUP.update(
        create_symbolvalue_to_midinote_lookup(source.instrumentgroup, version, midi_notes_file)
    )
    TAG_TO_POSITION_LOOKUP.update(create_tag_to_position_lookup())
    # TODO temporary solution in order to avoid circular imports. Should look for more elegant solution.
    SilenceMeta.TAG_TO_POSITION_LOOKUP = TAG_TO_POSITION_LOOKUP
    POSITION_TO_RANGE_LOOKUP.update(create_position_range_lookup(source.instrumentgroup, version, midi_notes_file))


def is_silent(gongan: Gongan, position: InstrumentPosition):
    no_occurrence = sum((beat.staves.get(position, []) for beat in gongan.beats), []) == []
    all_rests = all(note.pitch == Pitch.NONE for beat in gongan.beats for note in beat.staves.get(position, []))
    return no_occurrence or all_rests


def stave_to_string(stave: list[Note]) -> str:
    return "".join((n.symbol for n in stave))


def create_rest_stave(resttype: Stroke, duration: float) -> list[Note]:
    """Creates a stave with rests of the given type for the given duration.
    If the duration is non-integer, the stave will also contain half and/or quarter rests.

    Args:
        resttype (Stroke): the type of rest (SILENCE or EXTENSION)
        duration (float): the duration, which can be non-integer.

    Returns:
        list[Note]: _description_
    """
    # TODO exception handling
    whole_rest: Note = next((note for note in NOTE_LIST if note.stroke == resttype and note.total_duration == 1), None)
    attribute = "duration" if whole_rest.duration > 0 else "rest_after"
    return [whole_rest.model_copy(update={attribute: duration})]
    # half_rest = whole_rest.model_copy(
    #     update={"duration": whole_rest.duration / 2, "rest_after": whole_rest.rest_after / 2}
    # )
    # quarter_rest = whole_rest.model_copy(
    #     update={"duration": whole_rest.duration / 4, "rest_after": whole_rest.rest_after / 4}
    # )
    # rest_count = int(duration)
    # half_rest_count = int((duration - rest_count) * 2)
    # quarter_rest_count = int((duration - rest_count - 0.5 * half_rest_count) * 4)
    # rests = [copy(whole_rest)] * rest_count + [half_rest] * half_rest_count + [quarter_rest] * quarter_rest_count
    # return rests


def gongan_to_records(gongan: Gongan, skipemptylines: bool = True) -> list[dict[InstrumentPosition | int, list[str]]]:
    """Converts a gongan to a dict containing the notation for the individual beats.

    Args:
        gongan (Gongan): gongan to convert
        skipemptylines (bool, optional): if true, positions without content (only rests) are skipped. Defaults to True.

    Returns:
        list[dict[InstrumentPosition | int, list[str]]]: _description_
    """

    skip = []
    alias = dict()
    # If pemade and kantilan staves are identical, replace both positions with a single "GANGSA" position.
    for p_pos, k_pos in [
        (InstrumentPosition.PEMADE_POLOS, InstrumentPosition.KANTILAN_POLOS),
        (InstrumentPosition.PEMADE_SANGSIH, InstrumentPosition.KANTILAN_SANGSIH),
    ]:
        if (
            p_pos in gongan.beats[0].staves
            and k_pos in gongan.beats[0].staves
            and all(beat.staves[p_pos] == beat.staves[k_pos] for beat in gongan.beats)
        ):
            skip.append(k_pos)
            alias[p_pos] = "GANGSA_" + p_pos.value.split("_")[1]

    result = (
        [{InstrumentFields.POSITION: COMMENT, 1: comment} for comment in gongan.comments]
        + [
            {InstrumentFields.POSITION: METADATA, 1: metadata.data.model_dump_json(exclude_defaults=True)}
            for metadata in gongan.metadata
        ]
        + [
            {InstrumentFields.POSITION: alias.get(position, position)}
            | {beat.id: stave_to_string(beat.staves[position]) for beat in gongan.beats}
            for position in InstrumentPosition
            if position not in skip
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
    score_dict = sum((gongan_to_records(gongan) for gongan in score.gongans), [])
    score_df = pd.DataFrame.from_records(score_dict)
    filepath = path.join(
        score.source.datapath,
        score.source.outfilefmt.format(position="_CORRECTED", version="", ext="csv"),
    )
    score_df.to_csv(filepath, sep="\t", index=False, header=False, quoting=csv.QUOTE_NONE)


# Create lookup dicts based on the settings files (CSV)
#


def create_symbol_to_note_lookup(fromfile: str) -> dict[str, Note]:
    balifont_df = pd.read_csv(fromfile, sep="\t", quoting=csv.QUOTE_NONE)
    balifont_obj = balifont_df.where(pd.notnull(balifont_df), "NONE").to_dict(orient="records")
    balifont = [Note.model_validate(note_def) for note_def in balifont_obj]
    return {note.symbol: note for note in balifont}


def create_midinote_list(instrumentgroup: InstrumentGroup, version: MidiVersion, fromfile: str) -> list[MidiNote]:
    midinotes_df = pd.read_csv(fromfile, sep="\t", comment="#")
    # Convert pre-filled positions to a list of InstrumentPosition values.
    # Fill in empty position fields with all positions for the instrument type.
    mask = midinotes_df[MidiNotesFields.POSITIONS].isnull()
    midinotes_df.loc[mask, MidiNotesFields.POSITIONS] = midinotes_df.loc[mask, MidiNotesFields.INSTRUMENTTYPE].apply(
        lambda x: [p for p in InstrumentPosition if p.instrumenttype == x]
    )
    midinotes_df[MidiNotesFields.OCTAVE] = midinotes_df[MidiNotesFields.OCTAVE].replace(np.nan, value="NONE")
    midinotes_df[MidiNotesFields.REMARK] = midinotes_df[MidiNotesFields.REMARK].replace(np.nan, value="")
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
    return [MidiNote.model_validate(midi) for midi in midinotes_dict]


def create_symbolvalue_to_midinote_lookup(
    instrumentgroup: InstrumentGroup, version: MidiVersion, fromfile: str
) -> dict[tuple[InstrumentPosition, Pitch, Octave, Stroke], MIDIvalue]:
    midinotes = create_midinote_list(instrumentgroup, version=version, fromfile=fromfile)
    return {(midi.instrumenttype, midi.pitch, midi.octave, midi.stroke): midi for midi in midinotes}


def create_position_range_lookup(
    instrumentgroup: InstrumentGroup, midiversion: MidiVersion, fromfile: str
) -> dict[InstrumentPosition, tuple[Pitch, Octave, Stroke]]:
    midinotes = create_midinote_list(instrumentgroup, version=midiversion, fromfile=fromfile)
    lookup = {
        position: [(midi.pitch, midi.octave, midi.stroke) for midi in midinotes if position in midi.positions]
        for position in InstrumentPosition
    }
    return lookup


def create_tag_to_position_lookup(fromfile: str = TAGS_DEF_FILE) -> dict[InstrumentTag, list[InstrumentPosition]]:
    """Creates a dict that maps "free style" position tags to a list of InstumentPosition values

    Args:
        fromfile (str, optional): _description_. Defaults to TAGS_DEF_FILE.

    Returns:
        _type_: _description_
    """
    tags_dict = pd.read_csv(fromfile, sep="\t").to_dict(orient="records")
    tags = [InstrumentTag.model_validate(record) for record in tags_dict]
    lookup_dict = {t.tag: t.positions for t in tags}
    # Add all InstrumentPosition values and aggregations
    lookup_dict.update({pos.value: [pos] for pos in InstrumentPosition})
    lookup_dict.update(
        {
            "GANGSA_POLOS": [InstrumentPosition.PEMADE_POLOS, InstrumentPosition.KANTILAN_POLOS],
            "GANGSA_SANGSIH": [InstrumentPosition.PEMADE_SANGSIH, InstrumentPosition.KANTILAN_SANGSIH],
        }
    )
    return lookup_dict


if __name__ == "__main__":
    print(create_position_range_lookup(InstrumentGroup.GONG_KEBYAR, MidiVersion.MULTIPLE_INSTR, MIDI_NOTES_DEF_FILE))
