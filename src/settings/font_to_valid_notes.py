""" 
This module provides the valid combinations of note attributes as a list of records. The list is created
by combining the font and MIDI notes definitions and applying some logic. The result is a list of all
meaningful combinations of Position, Pitch, Octave, Stroke, Modifier, duration and rest_after values 
for Note objects, together with the corresponding combination of characters from the font. 
All Note objects should be created from this list. This will be enforced by the Note validator.

The result is intentionally returned as a list of records (NotationRecord = list[str, Any]) and not 
as a list of Note objects to enable the Note validator to import this module without causing a 
circular reference.
"""

import csv
import json
import re
from enum import StrEnum
from typing import Any

import numpy as np
import pandas as pd
from pydantic import BaseModel, ConfigDict

from src.common.constants import InstrumentType, Modifier, Pitch, Position, Stroke
from src.settings.classes import RunSettings
from src.settings.constants import MidiNotesFields, NoteFields
from src.settings.settings import get_run_settings


class AnyNote(BaseModel):
    # Class used to create valid note objects. None values are accepted here.
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
    # Class used to create notes with validated field values. Only int values may be None,
    # other values will raise an exception if missing, malformed or None (we use Pydantic to check this).
    # We don't use the Note class here to avoid circular references.
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

# Functions that should be applied to each field when processing the MIDI data
MIDI_FORMATTERS = {
    NoteFields.PITCH.value: lambda x: Pitch[x],
    NoteFields.STROKE.value: lambda x: Stroke[x],
    NoteFields.INSTRUMENTTYPE.value: lambda x: InstrumentType[x],
    NoteFields.PITCH.value: lambda x: Pitch[x],
    NoteFields.STROKE.value: lambda x: Stroke[x],
    NoteFields.MIDINOTE.value: lambda x: eval(x) if x.startswith("[") else [int(x)],
    NoteFields.SAMPLE.value: lambda x: "" if pd.isna(x) else x,
    NoteFields.SYMBOL.value: lambda x: "" if pd.isna(x) else x,
    NoteFields.ROOTNOTE.value: lambda x: "" if pd.isna(x) else x,
}
# Same for the font data
FONT_FORMATTERS = {
    NoteFields.PITCH.value: lambda x: Pitch[x],
    NoteFields.STROKE.value: lambda x: Stroke[x],
    NoteFields.MODIFIER.value: lambda x: Modifier[x],
}
DTYPES = {NoteFields.OCTAVE.value: "Int64"}


def to_list(value, el_type: type):
    # This method tries to to parse a string or a list of strings
    # into a list of `el_type` values.
    # el_type can only be `float` or a subclass of `StrEnum`.
    if isinstance(value, str):
        # Single string representing a list of strings: parse into a list of strings
        # First add double quotes around each list element.
        val = re.sub(r"([A-Za-z_][\w]*)", r'"\1"', value)
        value = json.loads(val)
    if isinstance(value, list):
        # List of strings: convert strings to enumtype objects.
        if all(isinstance(el, str) for el in value):
            return [el_type[el] if issubclass(el_type, StrEnum) else float(el) for el in value]
        elif all(isinstance(el, el_type) for el in value):
            # List of el_type: do nothing
            return value
    else:
        raise ValueError(f"Cannot convert value {value} to a list of {el_type}")


def create_note_records(run_settings: RunSettings) -> list[AnyNote]:
    """Creates a list of records containing all possible attribute combinations for a Note object.
       The records are created by combining the MIDI definitions and the font definitions files
       and will be used to validate the creation of new Note objects. This will ensure that any character combination
        that does not occur in this dict is considered invalid.

    Args:
        run_settings (RunSettings): run_settings, containing the location of font and MIDI note definitions.
    """

    def getmatch(
        note_record: AnyNote, fields: list[str], record_list: list[AnyNote], ismodifier: bool
    ) -> AnyNote | ModuleNotFoundError:
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
        INSTRUMENTTYPE := NoteFields.INSTRUMENTTYPE.value,
        POSITION := NoteFields.POSITION.value,
        PITCH := NoteFields.PITCH.value,
        OCTAVE := NoteFields.OCTAVE.value,
        STROKE := NoteFields.STROKE.value,
        MODIFIER := NoteFields.MODIFIER.value,
        SYMBOL := NoteFields.SYMBOL.value,
        DURATION := NoteFields.DURATION.value,
        REST_AFTER := NoteFields.REST_AFTER.value,
        MIDINOTE := NoteFields.MIDINOTE.value,
        SAMPLE := NoteFields.SAMPLE.value,
        ROOTNOTE := NoteFields.ROOTNOTE.value,
    ]
    INSTRUMENTGROUP = NoteFields.INSTRUMENTGROUP.value
    POSITIONS = MidiNotesFields.POSITIONS.value

    REST_STROKES = [Stroke.SILENCE, Stroke.EXTENSION]

    # READ MIDINOTES DATA
    midinotes_df = pd.read_csv(
        run_settings.midi.notes_filepath, sep="\t", comment="#", dtype=DTYPES, converters=MIDI_FORMATTERS
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
        run_settings.font.filepath, sep="\t", quoting=csv.QUOTE_NONE, dtype=DTYPES, converters=FONT_FORMATTERS
    )

    # MERGE BOTH TABLES
    notes_df = midinotes_df.merge(balifont_df, on=[PITCH, OCTAVE, STROKE], how="outer")[keep]
    notes_df[MODIFIER] = notes_df[MODIFIER].apply(lambda x: Modifier.NONE if pd.isna(x) else x)
    notes_df = notes_df.replace([np.nan], [None], regex=False)

    # CREATE SEPARATE NOTES, RESTS AND MODIFIERS LISTS.
    # The unmodified_notes list contains only notes without modifiers, i.e. notes that correspond with a single character
    midi_notes_dicts = notes_df[~pd.isna(notes_df[INSTRUMENTTYPE])].to_dict(orient="records")
    midi_notes = [AnyNote(**note) for note in midi_notes_dicts]

    rest_notes_dicts = notes_df[notes_df[STROKE].isin(REST_STROKES)].to_dict(orient="records")
    rest_notes = [AnyNote(**note) for note in rest_notes_dicts]

    modifiers_dicts = notes_df[
        pd.isna(notes_df[INSTRUMENTTYPE]) & (notes_df[PITCH] == "NONE") & (notes_df[MODIFIER] != "NONE")
    ].to_dict(orient="records")
    modifiers = [AnyNote(**note) for note in modifiers_dicts]

    global MODIFIERS
    MODIFIERS = modifiers

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
    # the notation, they will be needd later when the correct octave of grace notes is determined.
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
            # We previously matched on instrumenttype because matching on position might not find
            # all possible OPEN note pitches for the instrument (e.g. reyong positions).
            # So here we update the actual position in the match record.
            match = match.model_copy(update={POSITION: record.position})
        # Try adding an octave modifier
        if match and match.octave != record.octave:
            modifier = getmatch(record, [OCTAVE], modifiers, True)
            match = match.model_copy(
                update={SYMBOL: match.symbol + modifier.symbol, OCTAVE: (modifier.octave)} if modifier else {}
            )
            if match and modifier in unmatched:
                unmatched.remove(modifier)
        # Try adding a stroke modifier
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
    ) -> list[AnyNote]:
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


def get_font_characters(run_settings: RunSettings):
    return pd.read_csv(
        run_settings.font.filepath, sep="\t", quoting=csv.QUOTE_NONE, dtype=DTYPES, converters=FONT_FORMATTERS
    ).to_dict(orient="records")


def sort_chars(chars: str, sortingorder) -> str:
    return "".join(sorted(chars, key=lambda c: sortingorder.get(c, 99)))


if __name__ == "__main__":
    settings = get_run_settings()
    font = get_font_characters(settings)
    mod_list = list(Modifier)
    sortingorder = {sym[NoteFields.SYMBOL]: mod_list.index(sym[NoteFields.MODIFIER]) for sym in font}
    print([(n, o) for n, o in sortingorder.items() if o > 0])
    for chars in ["a_,/", "an<", "x:_"]:
        print(f"{chars} -> {sort_chars(chars, sortingorder)}")
