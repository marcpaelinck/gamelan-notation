import csv
from itertools import product
from os import path
from statistics import mode

import numpy as np
import pandas as pd

from src.common.classes import Beat, Gongan, MidiNote, Note, Preset, RunSettings, Score
from src.common.constants import (
    InstrumentGroup,
    InstrumentPosition,
    InstrumentType,
    MIDIvalue,
    NotationFont,
    Octave,
    Pitch,
    SpecialTags,
    Stroke,
)
from src.common.lookups import (
    MIDINOTE_LOOKUP,
    NOTE_LIST,
    POSITION_TO_RANGE_LOOKUP,
    PRESET_LOOKUP,
    SYMBOL_TO_NOTE_LOOKUP,
    SYMBOLVALUE_TO_MIDINOTE_LOOKUP,
    TAG_TO_POSITION_LOOKUP,
    InstrumentTag,
)
from src.common.metadata_classes import (
    GonganType,
    KempliMeta,
    MetaDataSwitch,
    SilenceMeta,
)
from src.settings.settings import (
    InstrumentFields,
    InstrumentTagFields,
    MidiNotesFields,
    PresetsFields,
    get_run_settings,
)


def initialize_lookups(run_settings: RunSettings) -> None:
    """Initializes lookup dicts and lists from settings files

    Args:
        instrumentgroup (InstrumentGroup): The type of orchestra (e.g. gong kebyar, semar pagulingan)
        version (Version):  Used to define which midi mapping to use from the midinotes.csv file.

    """
    # global SYMBOL_TO_NOTE_LOOKUP, NOTE_LIST, SYMBOLVALUE_TO_MIDINOTE_LOOKUP
    SYMBOL_TO_NOTE_LOOKUP.update(create_symbol_to_note_lookup(run_settings.font.filepath))
    NOTE_LIST.extend(list(SYMBOL_TO_NOTE_LOOKUP.values()))
    PRESET_LOOKUP.update(
        create_instrumentposition_to_preset_lookup(
            run_settings.instruments.instrumentgroup, run_settings.midi.presets_filepath
        )
    )
    MIDINOTE_LOOKUP.update(
        create_instrumentposition_to_midinote_lookup(
            run_settings.instruments.instrumentgroup, fromfile=run_settings.midi.notes_filepath
        )
    )
    midinotes_list = [note for notelist in MIDINOTE_LOOKUP.values() for note in notelist]
    SYMBOLVALUE_TO_MIDINOTE_LOOKUP.update(create_symbolvalue_to_midinote_lookup(midinotes_list))
    POSITION_TO_RANGE_LOOKUP.update(create_position_range_lookup(midinotes_list))
    TAG_TO_POSITION_LOOKUP.update(create_tag_to_position_lookup(run_settings.instruments))
    # TODO temporary solution in order to avoid circular imports. Should look for more elegant solution.
    SilenceMeta.TAG_TO_POSITION_LOOKUP = TAG_TO_POSITION_LOOKUP


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


def get_whole_rest_note(resttype: Stroke):
    return next((note for note in NOTE_LIST if note.stroke == resttype and note.total_duration == 1), None)


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
    notes = []
    whole_rest: Note = get_whole_rest_note(resttype)
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
        all_positions_occur_in_gongan = all(pos in gongan.beats[0].staves for pos in positions)
        all_positions_have_same_notation = all(
            all(beat.staves[pos] == beat.staves[positions[0]] for beat in gongan.beats) for pos in positions
        )
        if all_positions_occur_in_gongan and all_positions_have_same_notation:
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


def create_symbol_to_note_lookup(fromfile: str) -> dict[str, Note]:
    balifont_df = pd.read_csv(fromfile, sep="\t", quoting=csv.QUOTE_NONE)
    balifont_obj = balifont_df.where(pd.notnull(balifont_df), "NONE").to_dict(orient="records")
    balifont = [Note.model_validate(note_def) for note_def in balifont_obj]
    return {note.symbol: note for note in balifont}


def create_instrumentposition_to_midinote_lookup(
    instrumentgroup: InstrumentGroup, fromfile: str
) -> tuple[dict[InstrumentType, MidiNote], list[MidiNote]]:
    midinotes_df = pd.read_csv(fromfile, sep="\t", comment="#")
    # Convert pre-filled positions to a list of InstrumentPosition values.
    # Fill in empty position fields with all positions for the instrument type.
    mask = midinotes_df[MidiNotesFields.POSITIONS].isnull()
    midinotes_df.loc[mask, MidiNotesFields.POSITIONS] = midinotes_df.loc[mask, MidiNotesFields.INSTRUMENTTYPE].apply(
        lambda x: [p for p in InstrumentPosition if p.instrumenttype == x]
    )
    # midinote field can be either int or list[int]. Convert all int values in list[int].
    midinotes_df[MidiNotesFields.MIDINOTE] = midinotes_df[MidiNotesFields.MIDINOTE].apply(
        lambda x: eval(x) if x.startswith("[") else [int(x)]
    )

    # Treat missing values
    midinotes_df[MidiNotesFields.OCTAVE] = midinotes_df[MidiNotesFields.OCTAVE].replace(np.nan, value="NONE")
    midinotes_df[MidiNotesFields.REMARK] = midinotes_df[MidiNotesFields.REMARK].replace(np.nan, value="")
    midinotes_df[MidiNotesFields.SAMPLE] = midinotes_df[MidiNotesFields.SAMPLE].replace(np.nan, value="")
    midinotes_df[MidiNotesFields.ROOTNOTE] = midinotes_df[MidiNotesFields.ROOTNOTE].replace(np.nan, value=None)

    # Drop unrequired instrument groups and convert to dict
    midinotes_dict = (
        midinotes_df[midinotes_df[MidiNotesFields.INSTRUMENTGROUP] == instrumentgroup.value]
        .drop(MidiNotesFields.INSTRUMENTGROUP, axis="columns")
        .to_dict(orient="records")
    )
    # Convert to MidiNote objects
    midinotes = [MidiNote.model_validate(midinote) for midinote in midinotes_dict]
    instumenttypes = {midinote.instrumenttype for midinote in midinotes}
    return {
        instrumenttype: [midinote for midinote in midinotes if midinote.instrumenttype == instrumenttype]
        for instrumenttype in instumenttypes
    }


def create_instrumentposition_to_preset_lookup(
    instrumentgroup: InstrumentGroup, fromfile: str
) -> dict[InstrumentType, Preset]:
    presets_df = pd.read_csv(fromfile, sep="\t", quoting=csv.QUOTE_NONE)
    # Fill in empty position fields with a list of all positions for the instrument type.
    # Then "explode" (repeat row for each element in the position list)
    # TODO not yet working!!!!
    mask = presets_df[PresetsFields.POSITION].isnull()
    presets_df.loc[mask, PresetsFields.POSITION] = presets_df.loc[mask, PresetsFields.INSTRUMENTTYPE].apply(
        lambda x: [p for p in InstrumentPosition if p.instrumenttype == x]
    )
    presets_df = presets_df.explode(column=PresetsFields.POSITION, ignore_index=True)
    # Create a dict and cast items to Preset objects.
    presets_obj = (
        presets_df[presets_df[PresetsFields.INSTRUMENTGROUP] == instrumentgroup.value]
        .drop(PresetsFields.INSTRUMENTGROUP, axis="columns")
        .to_dict(orient="records")
    )
    presets = [Preset.model_validate(preset) for preset in presets_obj]
    return {preset.position: preset for preset in presets}


def create_symbolvalue_to_midinote_lookup_old(
    midinotes_list: list[MidiNote],
) -> dict[tuple[InstrumentPosition, Pitch, Octave, Stroke], MIDIvalue]:
    return {(midi.instrumenttype, midi.pitch, midi.octave, midi.stroke): midi for midi in midinotes_list}


def create_symbolvalue_to_midinote_lookup(
    midinotes_list: list[MidiNote],
) -> dict[tuple[InstrumentPosition, Pitch, Octave, Stroke], MIDIvalue]:
    retval = {
        (position, midi.pitch, midi.octave, midi.stroke): midi for midi in midinotes_list for position in midi.positions
    }
    return retval


def create_position_range_lookup(
    midinotes_list: list[MidiNote],
) -> dict[InstrumentPosition, list[tuple[Pitch, Octave, Stroke]]]:
    lookup = {
        position: [(midi.pitch, midi.octave, midi.stroke) for midi in midinotes_list if position in midi.positions]
        for position in InstrumentPosition
    }
    return lookup


def create_tag_to_position_lookup(
    instruments: RunSettings.InstrumentInfo,
) -> dict[InstrumentTag, list[InstrumentPosition]]:
    """Creates a dict that maps "free style" position tags to a list of InstumentPosition values

    Args:
        fromfile (str, optional): _description_. Defaults to TAGS_DEF_FILE.

    Returns:
        _type_: _description_
    """
    tags_dict = (
        pd.read_csv(instruments.tag_filepath, sep="\t")
        .drop(columns=[InstrumentTagFields.INFILE])
        .to_dict(orient="records")
    )
    tags_dict = (
        tags_dict
        + [
            {
                InstrumentTagFields.TAG: instr,
                InstrumentTagFields.POSITIONS: [pos for pos in InstrumentPosition if pos.instrumenttype == instr],
            }
            for instr in InstrumentType
        ]
        + [{InstrumentTagFields.TAG: pos, InstrumentTagFields.POSITIONS: [pos]} for pos in InstrumentPosition]
    )
    tags = [InstrumentTag.model_validate(record) for record in tags_dict]

    lookup_dict = {t.tag: t.positions for t in tags}

    return lookup_dict


def get_instrument_range(position: InstrumentPosition) -> list[tuple[Note, Octave]]:
    return [
        (note, oct)
        for (note, oct, stroke) in POSITION_TO_RANGE_LOOKUP[position]
        if stroke == POSITION_TO_RANGE_LOOKUP[position][0][2]
    ]


def get_nearest_note(
    pitch: Pitch,
    stroke: Stroke,
    duration: float = None,
    rest_after: float = None,
    octave: int = None,
    note_list: list[Note] = NOTE_LIST,
) -> Note:
    """Searches for the note with the best match

    Args:
        pitch (Pitch): _description_
        stroke (Stroke): _description_
        duration (float, optional): _description_. Defaults to None.
        rest_after (float, optional): _description_. Defaults to None.
        octave (int, optional): _description_. Defaults to None.
        note_list (list[Note], optional): _description_. Defaults to NOTE_LIST.

    Returns:
        Note: a note if found, otherwise None
    """
    stroke_alt = {stroke} | set({Stroke.OPEN} if stroke in [Stroke.ABBREVIATED, Stroke.MUTED] else {})
    duration_alt = {duration} | set({1} if duration else {})
    rest_after_alt = {rest_after} | set({0} if duration else {})
    octave_alt = {octave} | set({1} if octave else {})
    attempts = list(product(stroke_alt, duration_alt, rest_after_alt, octave_alt))

    for stroke_, duration_, rest_after_, octave_ in attempts:
        note = next(
            (
                note
                for note in note_list
                if (note.pitch == pitch)
                and (note.stroke == stroke_)
                and (duration_ == None or note.duration == duration_)
                and (rest_after_ == None or note.rest_after == rest_after_)
                and (octave_ == None or note.octave == octave_)
            ),
            None,
        )
        if note:
            return note
    return note


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
    initialize_lookups(settings)
