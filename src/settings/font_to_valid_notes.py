""" 
This module provides the valid combinations of note attributes as a list of records. The list is created
by combining the font and MIDI notes definitions and applying some logic. The result is a list of all
meaningful combinations of Position, Pitch, Octave, Stroke, Modifier, duration and rest_after values 
for Note objects, together with the corresponding combination of characters from the font. 
All Note objects should be created from this list. This will be enforced by the Note validator.

The result is intentionally returned as a list of records (list[str, Any]) and not as a list of Note objects
to enable the Note validator to use it without causing a circular reference.
"""

import csv
from typing import Any

import numpy as np
import pandas as pd
from pydantic import BaseModel, ConfigDict

from src.common.constants import InstrumentType, Modifier, Pitch, Position, Stroke
from src.common.utils_generic import to_list
from src.settings.classes import RunSettings
from src.settings.settings import FontFields, MidiNotesFields, get_run_settings


class NoteRecord(BaseModel):
    # Class used to generate all combinations of attributes. None values are accepted here.
    model_config = ConfigDict(frozen=True)

    instrumenttype: InstrumentType | None
    position: Position | None
    symbol: str | None
    pitch: Pitch
    octave: int | None
    stroke: Stroke
    duration: float | None
    rest_after: float | None
    modifier: Modifier
    midinote: list[int] | None
    rootnote: str | None
    sample: str | None


class ValidNote(BaseModel):
    # Class used to validate the record format. Only int values may be None.
    # We don't use the Note class for this to avoid circular references.
    model_config = ConfigDict(extra="forbid", frozen=True, revalidate_instances="always")

    instrumenttype: InstrumentType
    position: Position
    symbol: str
    pitch: Pitch
    octave: int | None
    stroke: Stroke
    duration: float | None
    rest_after: float | None
    modifier: Modifier
    midinote: list[int]
    rootnote: str
    sample: str


NoteDict = dict[str, Any]


def create_note_records(run_settings: RunSettings) -> list[NoteRecord]:
    """Creates a list of records containing all possible attribute combinations for a Note object.
       The records are created by combining the MIDI definitions and the font definitions files
       and will be used to validate the creation of new Note objects. This will ensure that any character combination
        that does not occur in this dict is considered invalid.

    Args:
        run_settings (RunSettings): run_settings, containing the location of font and MIDI note definitions.
    """

    def getmatch(
        note_record: NoteRecord, fields: list[str], record_list: list[NoteRecord], ismodifier: bool
    ) -> NoteRecord | ModuleNotFoundError:
        """Searches for a record in record_list with a value that matches the given fields of note_record.
        Args:
            note_record (NoteRecord): A dict containing note properties
            fields (list[str]): List of fields to match
            record_list (_type_):
            ismodifier (bool): True: record_list is a list of modifiers. False: record_list is a list of note records.
        Returns:
            NoteRecord | None: The note record if found.
        """
        found = next(
            (
                rec
                for rec in record_list
                # A grace note should never be returned: there is always a better equivalent.
                if all(
                    getattr(rec, f) == getattr(note_record, f)
                    and (note_record.stroke == Stroke.GRACE_NOTE or rec.stroke != Stroke.GRACE_NOTE)
                    for f in fields
                )
                # In case of a note, we are looking for a record that has a symbol value.
                and (
                    (ismodifier and rec.modifier != Modifier.NONE)
                    or (not ismodifier and rec.modifier == Modifier.NONE and rec.symbol)
                )
            ),
            None,
        )
        if found:
            # Create a copy of the record
            return found.model_copy()
        return None

    # Fields that should be returned
    keep = [
        INSTRUMENTTYPE := MidiNotesFields.INSTRUMENTTYPE,
        POSITION := "position",
        PITCH := MidiNotesFields.PITCH.value,
        OCTAVE := MidiNotesFields.OCTAVE.value,
        STROKE := MidiNotesFields.STROKE.value,
        MODIFIER := FontFields.MODIFIER.value,
        SYMBOL := FontFields.SYMBOL.value,
        DURATION := FontFields.DURATION.value,
        REST_AFTER := FontFields.REST_AFTER.value,
        MIDINOTE := MidiNotesFields.MIDINOTE.value,
        SAMPLE := MidiNotesFields.SAMPLE.value,
        ROOTNOTE := MidiNotesFields.ROOTNOTE.value,
    ]
    INSTRUMENTGROUP = MidiNotesFields.INSTRUMENTGROUP.value
    POSITIONS = MidiNotesFields.POSITIONS.value
    # Functions that should be applied to each field when processing the MIDI data
    midi_formatters = {
        PITCH: lambda x: Pitch[x],
        STROKE: lambda x: Stroke[x],
        INSTRUMENTTYPE: lambda x: InstrumentType[x],
        PITCH: lambda x: Pitch[x],
        STROKE: lambda x: Stroke[x],
        MIDINOTE: lambda x: eval(x) if x.startswith("[") else [int(x)],
        SAMPLE: lambda x: "" if pd.isna(x) else x,
        SYMBOL: lambda x: "" if pd.isna(x) else x,
        ROOTNOTE: lambda x: "" if pd.isna(x) else x,
    }
    # Same for the font data
    font_formatters = {
        PITCH: lambda x: Pitch[x],
        STROKE: lambda x: Stroke[x],
        MODIFIER: lambda x: Modifier[x],
    }
    dtypes = {OCTAVE: "Int64"}
    REST_STROKES = [Stroke.SILENCE, Stroke.EXTENSION]

    # READ MIDINOTES DATA
    midinotes_df = pd.read_csv(
        run_settings.midi.notes_filepath, sep="\t", comment="#", dtype=dtypes, converters=midi_formatters
    )
    # Filter on instrument group
    midinotes_df = midinotes_df[midinotes_df[INSTRUMENTGROUP] == run_settings.instruments.instrumentgroup.value].drop(
        columns=[INSTRUMENTGROUP]
    )
    # Convert pre-filled instrument positions to a list of Position values.
    # Fill in empty position fields with all positions for the instrument type.
    # Then 'explode' the DF: repeat each row for each position in the list.
    mask = midinotes_df[POSITIONS].isnull()
    midinotes_df.loc[~mask, POSITIONS] = midinotes_df.loc[~mask, POSITIONS].apply(lambda x: to_list(x, Position))
    midinotes_df.loc[mask, POSITIONS] = midinotes_df.loc[mask, INSTRUMENTTYPE].apply(
        lambda x: [p for p in Position if p.instrumenttype == x]
    )
    midinotes_df = midinotes_df.explode(column=[POSITIONS]).rename(columns={POSITIONS: POSITION})

    # READ FONT DATA
    balifont_df = pd.read_csv(
        run_settings.font.filepath, sep="\t", quoting=csv.QUOTE_NONE, dtype=dtypes, converters=font_formatters
    )

    # MERGE BOTH TABLES
    notes_df = midinotes_df.merge(balifont_df, on=[PITCH, OCTAVE, STROKE], how="outer")[keep]
    notes_df[MODIFIER] = notes_df[MODIFIER].apply(lambda x: Modifier.NONE if pd.isna(x) else x)
    notes_df = notes_df.replace([np.nan], [None], regex=False)

    # CREATE SEPARATE NOTES, RESTS AND MODIFIERS LISTS.
    # The unmodified_notes list contains only notes without modifiers, i.e. notes that correspond with a single character
    midi_notes_dicts = notes_df[~pd.isna(notes_df[INSTRUMENTTYPE])].to_dict(orient="records")
    midi_notes = [NoteRecord(**note) for note in midi_notes_dicts]

    rest_notes_dicts = notes_df[notes_df[STROKE].isin(REST_STROKES)].to_dict(orient="records")
    rest_notes = [NoteRecord(**note) for note in rest_notes_dicts]

    modifiers_dicts = notes_df[
        pd.isna(notes_df[INSTRUMENTTYPE]) & (notes_df[PITCH] == "NONE") & (notes_df[MODIFIER] != "NONE")
    ].to_dict(orient="records")
    modifiers = [NoteRecord(**note) for note in modifiers_dicts]

    unmatched = list()
    unmatched.extend(modifiers)
    note_list: list[ValidNote] = list()
    all_positions: list[Position] = set()

    # TRY TO MATCH UNMATCHED MIDI VALUES BY ADDING MODIFIERS.
    # The match is performed on the key (Pitch, Octave, Stroke) which has a unique notation equivalent.
    # Our aim is to match all the MIDI notes with a (combinations of) notation symbol(s).
    # This will result in a dict containing all valid character combinations and corresponding MIDI values.
    # Through the previous merge operation, the notes list already contains direct matches between
    # the MIDI notes table and the font table: these are 'single character' notes  that have a MIDI
    # note equivalent. The remaining MIDI notes need to be matched with a combination of symbols:
    # a 'pitch' symbol followed by one or more modifier symbols.
    # This process will also create octavated versions of grace notes. Though these should not occur in
    # the notation, the
    for record in midi_notes:
        # If the record has a symbol value, it was matched with a single-character note, and
        # we can immediately create a Note instance from it.
        # Otherwise try to combine the record with modifier records until a match is found
        if record.symbol or (record.pitch == Pitch.NONE and record.modifier == Modifier.NONE):
            match = record
        else:
            # Try to find a similar matched note that can be used as a starting point.
            # A grace note should never be selected as a match (this is checked in getmatch).
            match = getmatch(record, [INSTRUMENTTYPE, PITCH, STROKE], midi_notes, False) or getmatch(
                record, [INSTRUMENTTYPE, PITCH], midi_notes, False
            )
        modifier = None
        if match:
            # We matched on instrumenttype because position might not have all OPEN note pitches (e.g. reyong position).
            # So we must now update the actual position.
            match = match.model_copy(update={POSITION: record.position})
        if match and match.octave != record.octave:
            modifier = getmatch(record, [OCTAVE], modifiers, True)
            match = match.model_copy(
                update={SYMBOL: match.symbol + modifier.symbol, OCTAVE: (modifier.octave)} if modifier else {}
            )
            if match and modifier in unmatched:
                unmatched.remove(modifier)
        # Try to add a stroke modifier
        if match and match.stroke != record.stroke:
            modifier = getmatch(record, [STROKE], modifiers, True)
            match = match.model_copy(
                update={SYMBOL: match.symbol + modifier.symbol, STROKE: (modifier.stroke)} if modifier else {}
            )
            if match and modifier in unmatched:
                unmatched.remove(modifier)
        if match:
            # Copy the POSITION, SYMBOL, DURATION and REST_AFTER values from the match to the record
            new_note = record.model_copy(
                update={
                    POSITION: match.position,
                    SYMBOL: match.symbol,
                    DURATION: match.duration,
                    REST_AFTER: match.rest_after,
                }
            )
            note_list.append(ValidNote.model_validate(new_note.model_dump()))
            all_positions.add(new_note.position)
        else:
            # For debugging only: contains unmatched MIDI notes and modifiers.
            # The unmatched modifiers should be the ones that are created separately below (note value, tremolo and norot)
            # For the Semar Pagulingan, the octavation to octave 2 will also appear here.
            unmatched.append(record)

    # ADD NOTATION SYMBOLS THAT DON'T HAVE A MIDI NOTE EQUIVALENT

    # add rests, including halves and quarters, for each instrument position.
    for rest_record in rest_notes:
        for position in all_positions:
            record = rest_record.model_copy(
                update={
                    INSTRUMENTTYPE: position.instrumenttype,
                    POSITION: position,
                    MIDINOTE: [127],
                    ROOTNOTE: "",
                    SAMPLE: "",
                }
            )

            note_list.append(ValidNote(**record.model_dump()))

    def modified_notes(
        modifier_list: list[Modifier],
        note_filter: callable = None,
        stroke_updater: callable = None,
        duration_updater: callable = None,
        restafter_updater: callable = None,
    ) -> list[NoteRecord]:
        """Creates (pseudo-)notes by applying modifiers to a copy of previously created notes, and adds the new notes
        to the pos_char_dict.
        This function should be used to create notes for which there is no entry in the MIDI notes table.
        These notes will have to be synthesized in a later stage before the MIDI output can be generated.
        The arguments determine which notes should be copied from the pos_char_dict, and what the new attributes
        should be.

        Args:
            modifier_list (list[Modifier]): List of modifier to apply
            note_filter (callable | None): Arguments: note: Note. Filters for the notes for which to apply the modifiers. If None, no filter is applied.
            stroke_updater (callable | None): Arguments: note: Note, modifier: NoteRecord. Determines the new note's stroke value. If None, the note's value remains unchanged.
            duration_updater (callable | None): Arguments: note: Note, modifier: NoteRecord. Determines the new note's duration value.  If None, the note's value remains unchanged.
            restafter_updater (callable | None): _descrArguments: note: Note, modifier: NoteRecord. Determines the new note's rest_after value.  If None, the note's value remains unchanged.
        """
        modifier_records = [mod for mod in modifiers if mod.modifier in modifier_list]

        # Create modified notes by applying modifiers on each note that qualifies
        modified_notes = list()
        for note in note_list:
            if not note_filter or note_filter(note):
                for modifier in modifier_records:
                    newnote = note.model_copy(
                        update={
                            SYMBOL: note.symbol + modifier.symbol,
                            STROKE: note.stroke if not stroke_updater else stroke_updater(note, modifier),
                            DURATION: note.duration if not duration_updater else duration_updater(note, modifier),
                            REST_AFTER: note.rest_after if not restafter_updater else restafter_updater(note, modifier),
                        }
                    )
                    modified_notes.append(newnote)
        return modified_notes

    # Add notes with half and quarter duration
    MODIFIERS = [Modifier.HALF_NOTE, Modifier.QUARTER_NOTE]
    note_filter = lambda note: note.duration + note.rest_after == 1
    duration_updater = lambda note, mod: note.duration * (mod.duration + mod.rest_after)
    restafter_updater = lambda note, mod: note.rest_after * (mod.duration + mod.rest_after)
    short_notes = modified_notes(
        MODIFIERS, note_filter=note_filter, duration_updater=duration_updater, restafter_updater=restafter_updater
    )
    note_list.extend([ValidNote.model_validate(note) for note in short_notes])

    # Add tremolo variants for each whole-duration note. This will generate tremolo notes for all melodic instruments
    # Including pokok instruments. Undesired combinations can be excluded by modifying the regex filters of the notation parser.
    MODIFIERS = [Modifier.TREMOLO, Modifier.TREMOLO_ACCELERATING]
    note_filter = (
        lambda note: note.pitch != Pitch.NONE and note.duration + note.rest_after == 1 and note.stroke == Stroke.OPEN
    )
    stroke_updater = lambda note, mod: mod.stroke
    tremolo_notes = modified_notes(MODIFIERS, note_filter=note_filter, stroke_updater=stroke_updater)
    note_list.extend([ValidNote.model_validate(note) for note in tremolo_notes])

    # Add norot variants for each melodic note.
    MODIFIERS = [Modifier.NOROT]
    melodics = [Pitch.DING, Pitch.DONG, Pitch.DENG, Pitch.DEUNG, Pitch.DUNG, Pitch.DANG, Pitch.DAING]
    norot_positions = [
        pos
        for pos in Position
        if pos.instrumenttype
        in [
            InstrumentType.GENDERRAMBAT,
            InstrumentType.KANTILAN,
            InstrumentType.PEMADE,
            InstrumentType.REYONG,
            InstrumentType.TROMPONG,
            InstrumentType.UGAL,
        ]
    ]
    note_filter = (
        lambda note: note.pitch in melodics
        and note.duration + note.rest_after == 1
        and note.stroke == Stroke.OPEN
        and note.position in norot_positions
    )
    stroke_updater = lambda note, mod: mod.stroke
    norot_notes = modified_notes(MODIFIERS, note_filter=note_filter, stroke_updater=stroke_updater)
    note_list.extend([ValidNote.model_validate(note) for note in norot_notes])

    # Convert to generic records.
    note_record_list = [note.model_dump() for note in note_list]

    return note_record_list


def get_note_records(run_settings: RunSettings):
    return create_note_records(run_settings)


if __name__ == "__main__":
    settings = get_run_settings()
    notes = get_note_records(settings)
    print(set([(n["pitch"], n["octave"], n["stroke"], n["modifier"]) for n in notes if not n["instrumenttype"]]))