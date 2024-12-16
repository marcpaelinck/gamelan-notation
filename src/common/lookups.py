f"""Separate location for lookup tables, which are populated with methods in utils.py.
    This construct enables to avoid circular references when importing the variables.
"""

import csv
from collections import defaultdict

import numpy as np
import pandas as pd

from src.common.classes import InstrumentTag, MidiNote, NotationModel, Note, Preset
from src.common.constants import (
    Duration,
    DynamicLevel,
    InstrumentGroup,
    InstrumentType,
    Modifier,
    NoteRecord,
    Octave,
    Pitch,
    Position,
    Stroke,
    Velocity,
)
from src.common.logger import get_logger
from src.settings.classes import RunSettings
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
    TAG_TO_POSITION: dict[InstrumentTag, list[Position]] = dict()  # KEEP
    INSTRUMENT_TO_MIDINOTE: dict[InstrumentType, list[MidiNote]] = dict()  # DELETE
    # P_O_S stands for Pitch, Octave, Stroke
    POSITION_P_O_S_TO_NOTE: dict[
        Position, dict[tuple[Pitch, Octave, Stroke], dict[tuple[Duration, Duration], Note]]
    ] = dict()
    POSITION_CHARS_TO_NOTELIST: dict[(Position, str), Note]
    DYNAMICS_TO_VELOCITY: dict[DynamicLevel, Velocity]
    DEFAULT_DYNAMICS: DynamicLevel

    def __init__(self, run_settings: RunSettings) -> None:
        """Initializes lookup dicts and lists from settings files

        Args:
            instrumentgroup (InstrumentGroup): The type of orchestra (e.g. gong kebyar, semar pagulingan)
            version (Version):  Used to define which midi mapping to use from the midinotes.csv file.

        """
        # self.TEST = self.create_instrumentposition_to_midinote_lookup_test(
        #     run_settings.instruments.instrumentgroup, fromfile=run_settings.midi.notes_filepath
        # )
        self.INSTRUMENT_TO_PRESET.update(
            self._create_instrumentposition_to_preset_lookup(
                run_settings.instruments.instrumentgroup, run_settings.midi.presets_filepath
            )
        )
        self.TAG_TO_POSITION.update(self._create_tag_to_position_lookup(run_settings.instruments))
        self.INSTRUMENT_TO_MIDINOTE.update(
            self._create_instrumentposition_to_midinote_lookup(
                run_settings.instruments.instrumentgroup, fromfile=run_settings.midi.notes_filepath
            )
        )
        self.POSITION_P_O_S_TO_NOTE = self._create_position_p_o_s_to_note_lookup(run_settings)
        self.POSITION_CHARS_TO_NOTELIST = {
            (position, note.symbol): note
            for position, P_O_S in self.POSITION_P_O_S_TO_NOTE.items()
            for props in P_O_S.values()
            for note in props.values()
        }
        self.DYNAMICS_TO_VELOCITY = run_settings.midi.dynamics
        self.DEFAULT_DYNAMICS = run_settings.midi.default_dynamics

    def _create_instrumentposition_to_midinote_lookup(
        self, instrumentgroup: InstrumentGroup, fromfile: str
    ) -> tuple[dict[InstrumentType, MidiNote], list[MidiNote]]:
        midinotes_df = pd.read_csv(fromfile, sep="\t", comment="#")
        # Convert pre-filled positions to a list of Position values.
        # Fill in empty position fields with all positions for the instrument type.
        mask = midinotes_df[MidiNotesFields.POSITIONS].isnull()
        midinotes_df.loc[mask, MidiNotesFields.POSITIONS] = midinotes_df.loc[
            mask, MidiNotesFields.INSTRUMENTTYPE
        ].apply(lambda x: [p for p in Position if p.instrumenttype == x])
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

    def _create_instrumentposition_to_preset_lookup(
        self, instrumentgroup: InstrumentGroup, fromfile: str
    ) -> dict[InstrumentType, Preset]:
        presets_df = pd.read_csv(fromfile, sep="\t", quoting=csv.QUOTE_NONE)
        # Fill in empty position fields with a list of all positions for the instrument type.
        # Then "explode" (repeat row for each element in the position list)
        # TODO not yet working!!!!
        mask = presets_df[PresetsFields.POSITION].isnull()
        presets_df.loc[mask, PresetsFields.POSITION] = presets_df.loc[mask, PresetsFields.INSTRUMENTTYPE].apply(
            lambda x: [p for p in Position if p.instrumenttype == x]
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

    def _create_tag_to_position_lookup(
        self,
        instruments: RunSettings.InstrumentInfo,
    ) -> dict[InstrumentTag, list[Position]]:
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
                    InstrumentTagFields.POSITIONS: [pos for pos in Position if pos.instrumenttype == instr],
                }
                for instr in InstrumentType
            ]
            + [{InstrumentTagFields.TAG: pos, InstrumentTagFields.POSITIONS: [pos]} for pos in Position]
        )
        tags = [InstrumentTag.model_validate(record) for record in tags_dict]

        lookup_dict = {t.tag: t.positions for t in tags}

        return lookup_dict

    def _create_position_p_o_s_to_note_lookup(
        self, run_settings: RunSettings
    ) -> dict[Position, dict[tuple[Pitch, Octave, Stroke], Note]]:
        """Creates the POSITION_P_O_S_TO_NOTE dict. This dict contains all possible Notes and should be used to validate/create
           new Note instances. The dict is created by combining the MIDI definitions and the font definitions files
           and will be the base for other lookups, such as the charater-to-note lookup.
           This will help validate the notation: any character combination that does not occur in this dict will be considered
           invalid. The dict is organized by instrument position. This will ensure that each note belongs to the range
           of an instrument or position.

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
            found = next(
                (
                    rec
                    for rec in record_list
                    # A grace note should never be returned: there is always a better equivalent.
                    if all(rec[f] == note_record[f] and rec[STROKE] != Stroke.GRACE_NOTE for f in fields)
                    # In case of a note, we are looking for a record that has a symbol value.
                    and (
                        (ismodifier and rec[MODIFIER] != Modifier.NONE)
                        or (not ismodifier and rec[MODIFIER] == Modifier.NONE and rec[SYMBOL])
                    )
                ),
                None,
            )
            if found:
                # Create a copy of the record
                return found.copy()
            return None

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
        # Convert pre-filled instrument positions to a list of Position values with the NotationModel.to_list method.
        # Fill in empty position fields with all positions for the instrument type.
        # Then 'explode' the DF: repeat each row for each position in the list.
        mask = midinotes_df[POSITIONS].isnull()
        midinotes_df.loc[~mask, POSITIONS] = midinotes_df.loc[~mask, POSITIONS].apply(
            lambda x: NotationModel.to_list(x, Position)
        )
        midinotes_df.loc[mask, POSITIONS] = midinotes_df.loc[mask, MidiNotesFields.INSTRUMENTTYPE].apply(
            lambda x: [p for p in Position if p.instrumenttype == x]
        )
        midinotes_df = midinotes_df.explode(column=[POSITIONS]).rename(columns={POSITIONS: POSITION})

        # READ FONT DATA
        balifont_df = pd.read_csv(
            run_settings.font.filepath, sep="\t", quoting=csv.QUOTE_NONE, dtype=dtypes, converters=font_converters
        )

        # MERGE BOTH TABLES
        notes_df = midinotes_df.merge(balifont_df, on=[PITCH, OCTAVE, STROKE], how="outer")[keep]
        notes_df[MODIFIER] = notes_df[MODIFIER].apply(lambda x: Modifier.NONE if pd.isna(x) else x)

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
        # The match is performed on the key (Pitch, Octave, Stroke) which has a unique notation equivalent.
        # Our aim is to match all the MIDI notes with a (combinations of) notation symbol(s).
        # This will result in a dict containing all valid character combinations and corresponding MIDI values.
        # Through the previous merge operation, the notes list already contains direct matches between
        # the MIDI notes table and the font table: these are 'single character' notes  that have a MIDI
        # note equivalent. The remaining MIDI notes need to be matched with a combination of symbols:
        # a 'pitch' symbol followed by one or more modifier symbols.
        for record in notes:
            # If the record has a symbol value, it was matched with a single-character note, and
            # we can immediately create a Note instance from it.
            # Otherwise try to combine the record with modifier records until a match is found
            if record[SYMBOL] or (record[PITCH] == Pitch.NONE and record[MODIFIER] == Modifier.NONE):
                match = record
            else:
                # Try to find a similar matched note that can be used as a starting point.
                # A grace note should never be selected as a match (this is checked in getmatch).
                match = getmatch(record, [INSTRUMENTTYPE, PITCH, STROKE], notes, False) or getmatch(
                    record, [INSTRUMENTTYPE, PITCH], notes, False
                )
            modifier = None
            if match:
                # We matched on instrumenttype because position might not have all OPEN note pitches (e.g. reyong position).
                # So we must now update the actual position.
                match[POSITION] = record[POSITION]
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
                # Copy the SYMBOL, DURATION and REST_AFTER values from the match to the record
                newrec = record.copy()
                newrec[SYMBOL], newrec[DURATION], newrec[REST_AFTER] = (
                    match[SYMBOL],
                    match[DURATION],
                    match[REST_AFTER],
                )
                newrec = newrec | {POSITION: match[POSITION], "_validate_range": False}
                P_O_S = (newrec[PITCH], newrec[OCTAVE], newrec[STROKE])
                DUR = (newrec[DURATION], newrec[REST_AFTER])
                pos_char_dict[newrec[POSITION]][P_O_S][DUR] = Note.model_validate(newrec) if record else None
            else:
                # For debugging only: contains unmatched MIDI notes and modifiers.
                # The unmatched modifiers should be the ones that are created separately below (note value, tremolo and norot)
                # For the Semar Pagulingan, the octavation to octave 2 will also appear here.
                unmatched.append(record)

        # ADD NOTATION SYMBOLS THAT DON'T HAVE A MIDI NOTE EQUIVALENT

        # add rests, including halves and quarterss.
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
                record[INSTRUMENTTYPE] = position.instrumenttype
                rest = Note.model_validate(record)
                P_O_S = (record[PITCH], record[OCTAVE], record[STROKE])
                pos_char_dict[position][P_O_S][rest.duration, rest.rest_after] = rest

        def add_modified_notes(
            modifier_list: list[Modifier],
            note_filter: callable = None,
            stroke_updater: callable = None,
            duration_updater: callable = None,
            restafter_updater: callable = None,
        ) -> None:
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
            modifier_records = [mod for mod in modifiers if mod[MODIFIER] in modifier_list]

            # Select the note properties for which the modifier applies
            keys = [
                (pos, p, o, s, d, r)
                for pos, p_o_s_dict in pos_char_dict.items()
                for (p, o, s), dur_dict in p_o_s_dict.items()
                for (d, r) in dur_dict.keys()
            ]

            # Create modified notes
            for pos, pitch, oct, stroke, dur, sil in keys:
                note: Note = pos_char_dict[pos][pitch, oct, stroke][dur, sil]
                if not note_filter or note_filter(note):
                    for modifier in modifier_records:
                        newnote = note.model_copy(
                            update={
                                "symbol": note.symbol + modifier[SYMBOL],
                                "stroke": note.stroke if not stroke_updater else stroke_updater(note, modifier),
                                "duration": (
                                    note.duration if not duration_updater else duration_updater(note, modifier)
                                ),
                                "rest_after": (
                                    note.rest_after if not restafter_updater else restafter_updater(note, modifier)
                                ),
                            }
                        )
                        pos_char_dict[pos][pitch, oct, newnote.stroke][newnote.duration, newnote.rest_after] = newnote

        # Add notes with half and quarter duration
        MODIFIERS = [Modifier.HALF_NOTE, Modifier.QUARTER_NOTE]
        note_filter = lambda note: note.total_duration == 1
        duration_updater = lambda note, mod_rec: note.duration * (mod_rec[DURATION] + mod_rec[REST_AFTER])
        restafter_updater = lambda note, mod_rec: note.rest_after * (mod_rec[DURATION] + mod_rec[REST_AFTER])
        add_modified_notes(
            MODIFIERS, note_filter=note_filter, duration_updater=duration_updater, restafter_updater=restafter_updater
        )

        # Add tremolo variants for each whole-duration note (norot only to melodic notes)
        MODIFIERS = [Modifier.TREMOLO, Modifier.TREMOLO_ACCELERATING]
        note_filter = lambda note: note.pitch != Pitch.NONE and note.stroke == Stroke.OPEN and note.total_duration == 1
        stroke_updater = lambda note, mod: mod[STROKE]
        add_modified_notes(MODIFIERS, note_filter=note_filter, stroke_updater=stroke_updater)

        # Add norot variants for each melodic note.
        MODIFIERS = [Modifier.NOROT]
        melodics = [Pitch.DING, Pitch.DONG, Pitch.DENG, Pitch.DEUNG, Pitch.DUNG, Pitch.DANG, Pitch.DAING]
        positions = [
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
            and note.stroke == Stroke.OPEN
            and note.total_duration == 1
            and note.position in positions
        )
        stroke_updater = lambda note, mod: mod[STROKE]
        add_modified_notes(MODIFIERS, note_filter=note_filter, stroke_updater=stroke_updater)

        return pos_char_dict

    def get_note(
        self,
        position: Position,
        pitch: Pitch,
        octave: Octave,
        stroke: Stroke,
        duration: Duration,
        rest_after: Duration,
    ) -> Note:
        note = (
            self.POSITION_P_O_S_TO_NOTE.get(position, {})
            .get((pitch, octave, stroke), {})
            .get((duration, rest_after), None)
        )
        if not note:
            if not any(
                (p, o) for p, o, _ in self.POSITION_P_O_S_TO_NOTE[position].keys() if p == pitch and o == octave
            ):
                msg = f"{pitch} octave={octave} is not in the range of {position} "
            else:
                msg = f"{pitch} octave={octave}, {stroke} duration={duration} rest-after={rest_after} not in range of {position}"
            self.log(msg)
        return note


run_settings = get_run_settings()
LOOKUP = Lookup(run_settings)
