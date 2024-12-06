f"""Separate location for lookup tables, which are populated with methods in utils.py.
    This construct enables to avoid circular references when importing the variables.
"""

import csv
from collections import defaultdict

import numpy as np
import pandas as pd

from src.common.classes import InstrumentTag, MidiNote, Note, Preset, RunSettings
from src.common.constants import (
    Duration,
    InstrumentGroup,
    InstrumentPosition,
    InstrumentType,
    MIDIvalue,
    Modifier,
    NoteRecord,
    Octave,
    Pitch,
    Stroke,
)
from src.common.logger import get_logger
from src.settings.settings import (
    FontFields,
    InstrumentTagFields,
    MidiNotesFields,
    PresetsFields,
    get_run_settings,
)

logger = logger = get_logger(__name__)


class Lookup:
    INSTRUMENT_TO_PRESET: dict[InstrumentType, Preset] = dict()  # KEEP
    POSITION_P_O_S_TO_NOTE: dict[
        InstrumentPosition, dict[tuple[Pitch, Octave, Stroke], dict[tuple[Duration, Duration], Note]]
    ] = dict()
    TAG_TO_POSITION: dict[InstrumentTag, list[InstrumentPosition]] = dict()  # KEEP

    INSTRUMENT_TO_MIDINOTE: dict[InstrumentType, list[MidiNote]] = dict()  # DELETE

    # combine with POSITION_TO_NOTERANGE
    def __init__(self, run_settings: RunSettings) -> None:
        """Initializes lookup dicts and lists from settings files

        Args:
            instrumentgroup (InstrumentGroup): The type of orchestra (e.g. gong kebyar, semar pagulingan)
            version (Version):  Used to define which midi mapping to use from the midinotes.csv file.

        """
        self.INSTRUMENT_TO_PRESET.update(
            self.create_instrumentposition_to_preset_lookup(
                run_settings.instruments.instrumentgroup, run_settings.midi.presets_filepath
            )
        )
        self.INSTRUMENT_TO_MIDINOTE.update(
            self.create_instrumentposition_to_midinote_lookup(
                run_settings.instruments.instrumentgroup, fromfile=run_settings.midi.notes_filepath
            )
        )
        self.TAG_TO_POSITION.update(self.create_tag_to_position_lookup(run_settings.instruments))
        self.POSITION_P_O_S_TO_NOTE = self.create_position_p_o_s_to_note_lookup(run_settings)
        self.POSITION_CHARS_TO_NOTELIST = {
            (position, note.symbol): note
            for position, P_O_S in self.POSITION_P_O_S_TO_NOTE.items()
            for props in P_O_S.values()
            for note in props.values()
        }
        self.POSITION_TO_NOTERANGE = {
            position: [props for props in propdict] for position, propdict in self.POSITION_P_O_S_TO_NOTE.items()
        }

    def create_symbol_to_note_lookup(self, fromfile: str) -> dict[str, Note]:
        balifont_df = pd.read_csv(fromfile, sep="\t", quoting=csv.QUOTE_NONE)
        balifont_obj = balifont_df.where(pd.notnull(balifont_df), "NONE").to_dict(orient="records")
        balifont = [Note.model_validate(note_def | {"_validate_range": False}) for note_def in balifont_obj]
        return {note.symbol: note for note in balifont}

    def create_instrumentposition_to_midinote_lookup(
        self, instrumentgroup: InstrumentGroup, fromfile: str
    ) -> tuple[dict[InstrumentType, MidiNote], list[MidiNote]]:
        midinotes_df = pd.read_csv(fromfile, sep="\t", comment="#")
        # Convert pre-filled positions to a list of InstrumentPosition values.
        # Fill in empty position fields with all positions for the instrument type.
        mask = midinotes_df[MidiNotesFields.POSITIONS].isnull()
        midinotes_df.loc[mask, MidiNotesFields.POSITIONS] = midinotes_df.loc[
            mask, MidiNotesFields.INSTRUMENTTYPE
        ].apply(lambda x: [p for p in InstrumentPosition if p.instrumenttype == x])
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
        self, instrumentgroup: InstrumentGroup, fromfile: str
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
        # self.create a dict and cast items to Preset objects.
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

    def create_tag_to_position_lookup(
        self,
        instruments: RunSettings.InstrumentInfo,
    ) -> dict[InstrumentTag, list[InstrumentPosition]]:
        """self.creates a dict that maps "free style" position tags to a list of InstumentPosition values

        Args:
            fromfile (str, optional): _description_. Defaults to TAGS_DEF_FILE.

        Returns:
            _type_: _description_
        """
        try:
            tags_dict = (
                pd.read_csv(instruments.tag_filepath, sep="\t")
                .drop(columns=[InstrumentTagFields.INFILE])
                .to_dict(orient="records")
            )
        except:
            logger.error(
                f"Error importing file {instruments.tag_filepath}. Check that it exists and that it is properly formatted."
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

    def create_position_p_o_s_to_note_lookup(
        self, run_settings: RunSettings
    ) -> dict[InstrumentPosition, dict[tuple[Pitch, Octave, Stroke], Note]]:
        """Creates the POSITION_P_O_S_TO_NOTE dict. This dict contains all possible Notes and should be used to create new Note objects.
        Args:
            run_settings (RunSettings): run_settings, containing the instrument group.
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
            return next(
                (
                    rec
                    for rec in record_list
                    if all(rec[f] == note_record[f] for f in fields)
                    # In case of a note, we are looking for a record that has a symbol value.
                    and (ismodifier or (rec[MODIFIER] == Modifier.NONE and rec[SYMBOL]))
                ),
                None,
            )

        keep = [
            INSTRUMENTTYPE := MidiNotesFields.INSTRUMENTTYPE,
            POSITION := "position",
            PITCH := MidiNotesFields.PITCH,
            OCTAVE := MidiNotesFields.OCTAVE,
            STROKE := MidiNotesFields.STROKE,
            MODIFIER := FontFields.MODIFIER,
            SYMBOL := FontFields.SYMBOL,
            DURATION := FontFields.DURATION,
            REST_AFTER := FontFields.REST_AFTER,
            MIDINOTE := MidiNotesFields.MIDINOTE,
            SAMPLE := MidiNotesFields.SAMPLE,
            ROOTNOTE := MidiNotesFields.ROOTNOTE,
        ]
        INSTRUMENTGROUP = MidiNotesFields.INSTRUMENTGROUP
        POSITIONS = MidiNotesFields.POSITIONS
        midi_converters = {
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
        font_converters = {
            PITCH: lambda x: Pitch[x],
            STROKE: lambda x: Stroke[x],
            MODIFIER: lambda x: Modifier[x],
        }
        dtypes = {OCTAVE: "Int64"}

        # READ MIDINOTES TABLE
        midinotes_df = pd.read_csv(
            run_settings.midi.notes_filepath, sep="\t", comment="#", dtype=dtypes, converters=midi_converters
        )
        # Filter on instrument group
        midinotes_df = midinotes_df[
            midinotes_df[INSTRUMENTGROUP] == run_settings.instruments.instrumentgroup.value
        ].drop(MidiNotesFields.INSTRUMENTGROUP, axis="columns")
        # Convert pre-filled instrument positions to a list of InstrumentPosition values.
        # Fill in empty position fields with all positions for the instrument type.
        # Then 'explode' the DF: repeat each row for each position in the list.
        mask = midinotes_df[POSITIONS].isnull()
        midinotes_df.loc[mask, POSITIONS] = midinotes_df.loc[mask, MidiNotesFields.INSTRUMENTTYPE].apply(
            lambda x: [p for p in InstrumentPosition if p.instrumenttype == x]
        )
        midinotes_df = midinotes_df.explode(column=[POSITIONS]).rename(columns={POSITIONS: POSITION})

        # READ FONT DATA
        balifont_df = pd.read_csv(
            run_settings.font.filepath, sep="\t", quoting=csv.QUOTE_NONE, dtype=dtypes, converters=font_converters
        )

        # MERGE BOTH TABLES
        notes_df = midinotes_df.merge(balifont_df, on=[PITCH, OCTAVE, STROKE], how="outer")[keep]

        # CREATE SEPARATE NOTES AND MODIFIERS DICTS
        notes = (
            notes_df[~pd.isna(notes_df[MidiNotesFields.INSTRUMENTTYPE])]
            .replace([np.nan], [None], regex=False)
            .to_dict(orient="records")
        )
        modifiers = notes_df[
            pd.isna(notes_df[MidiNotesFields.INSTRUMENTTYPE])
            & (notes_df[FontFields.PITCH] == "NONE")
            & (notes_df[FontFields.MODIFIER] != "NONE")
        ].to_dict(orient="records")

        unmatched = list()
        unmatched.extend(modifiers)
        pos_char_dict = defaultdict(lambda: defaultdict(dict))
        # TRY TO MATCH UNMATCHED MIDI VALUES BY ADDING MODIFIERS.
        # The notes list contains direct matches between the MIDI notes table and the font table.
        # The latter only contains single-character notes. However some notes should be written with more
        # than one symbol (a 'pitch' symbol followed by one or more modifier symbols).
        for record in notes:
            # If the record has a symbol value, it represents a single-character note or a rest.
            # We can immediately create a note from it.
            if record[SYMBOL] or (record[PITCH] == Pitch.NONE and record[MODIFIER] == Modifier.NONE):
                match = record
            else:
                # Try to combine the record with modifier records until a match is found
                # Look for a note record with the same pitch, that has a symbol value.
                match = getmatch(record, [POSITION, PITCH], notes, False)
                modifier = None
                # Try to add an octave modifier
                if match and match[OCTAVE] != record[OCTAVE]:
                    modifier = getmatch(record, [OCTAVE], modifiers, True)
                    match = match | (
                        {SYMBOL: match[SYMBOL] + modifier[SYMBOL], OCTAVE: (modifier[OCTAVE])} if modifier else {}
                    )
                    if match and modifier in unmatched:
                        unmatched.remove(modifier)
                # Try to add a stroke modifier
                if match and match[STROKE] != record[STROKE]:
                    modifier = getmatch(record, [STROKE], modifiers, True)
                    match = match | (
                        {SYMBOL: match[SYMBOL] + modifier[SYMBOL], STROKE: (modifier[STROKE])} if modifier else {}
                    )
                    if match and modifier in unmatched:
                        unmatched.remove(modifier)
            if match:
                match = match | {POSITION: match[POSITION], "_validate_range": False}
                P_O_S = (match[PITCH], match[OCTAVE], match[STROKE])
                DUR = (match[DURATION], match[REST_AFTER])
                pos_char_dict[match[POSITION]][P_O_S][DUR] = Note.model_validate(match) if match else None
            else:
                unmatched.append(record)

        # ADD RESTS, INCLUDING HALVES AND QUARTERSS
        REST_STROKES = [Stroke.SILENCE, Stroke.EXTENSION]
        rests = (
            notes_df[notes_df[STROKE].isin(REST_STROKES)]
            .replace([np.nan], [None], regex=False)
            .drop(columns=[MIDINOTE, ROOTNOTE, SAMPLE])
            .to_dict(orient="records")
        )
        for record in rests:
            for position in pos_char_dict.keys():
                record[POSITION] = position
                rest = Note.model_validate(record)
                P_O_S = (record[PITCH], record[OCTAVE], record[STROKE])
                pos_char_dict[position][P_O_S][rest.duration, rest.rest_after] = rest

        # ADD NOTES WITH HALF AND QUARTER DURATION
        NOTEVALUE_MODIFIERS = [Modifier.HALF_NOTE, Modifier.QUARTER_NOTE]
        notevalue_modifiers = (
            notes_df[notes_df[MODIFIER].isin(NOTEVALUE_MODIFIERS)]
            .replace([np.nan], [None], regex=False)
            .to_dict(orient="records")
        )
        keys = [
            (pos, p, o, s, d, r)
            for pos, p_o_s_dict in pos_char_dict.items()
            for (p, o, s), dur_dict in p_o_s_dict.items()
            for (d, r) in dur_dict.keys()
        ]
        for pos, pitch, oct, stroke, dur, sil in keys:
            for modifier in notevalue_modifiers:
                factor = modifier[DURATION] + modifier[REST_AFTER]
                note = pos_char_dict[pos][pitch, oct, stroke][dur, sil]
                newnote = note.model_copy(
                    update={
                        "symbol": note.symbol + modifier[SYMBOL],
                        "duration": note.duration * factor,
                        "rest_after": note.rest_after * factor,
                    }
                )
                pos_char_dict[pos][pitch, oct, stroke][newnote.duration, newnote.rest_after] = newnote

        # ADD TREMOLO VARIANTS FOR EACH WHOLE-DURATION NOTE
        TREMOLO_STROKES = [Stroke.TREMOLO, Stroke.TREMOLO_ACCELERATING]
        tremolo_modifiers = (
            notes_df[notes_df[STROKE].isin(TREMOLO_STROKES)]
            .replace([np.nan], [None], regex=False)
            .to_dict(orient="records")
        )
        keys = [
            (pos, p, o, s, d, r)
            for pos, p_o_s_dict in pos_char_dict.items()
            for (p, o, s), dur_dict in p_o_s_dict.items()
            for (d, r) in dur_dict.keys()
            if p != Pitch.NONE and d + r == 1
        ]
        for pos, pitch, oct, stroke, dur, sil in keys:
            for tremolo in tremolo_modifiers:
                note = pos_char_dict[pos][pitch, oct, stroke][dur, sil]
                newnote = note.model_copy(
                    update={
                        "symbol": note.symbol + tremolo[SYMBOL],
                        "stroke": tremolo,
                        "duration": note.duration,
                        "rest_after": note.rest_after,
                    }
                )
                pos_char_dict[pos][pitch, oct, tremolo[STROKE]][newnote.duration, newnote.rest_after] = newnote

        return pos_char_dict


run_settings = get_run_settings()
LOOKUP = Lookup(run_settings)
