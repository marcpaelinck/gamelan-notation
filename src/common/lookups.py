"""Separate location for lookup tables, which are populated with methods in utils.py.
    This construct enables to avoid circular references when importing the variables.
"""

import csv

import numpy as np
import pandas as pd

from src.common.classes import InstrumentTag, MidiNote, Note, Preset, RunSettings
from src.common.constants import (
    InstrumentGroup,
    InstrumentPosition,
    InstrumentType,
    MIDIvalue,
    Octave,
    Pitch,
    Stroke,
)
from src.common.logger import get_logger
from src.common.metadata_classes import MetaDataBaseType
from src.settings.settings import (
    InstrumentTagFields,
    MidiNotesFields,
    PresetsFields,
    get_run_settings,
)

logger = logger = get_logger(__name__)


class Lookup:
    SYMBOL_TO_NOTE: dict[str, Note] = dict()
    NOTE_LIST: list[Note] = list()
    SYMBOLVALUE_TO_MIDINOTE: dict[tuple[InstrumentPosition, Pitch, Octave, Stroke], MidiNote] = dict()
    INSTRUMENT_TO_PRESET: dict[InstrumentType, Preset] = dict()
    INSTRUMENT_TO_MIDINOTE: dict[InstrumentType, MidiNote] = dict()
    TAG_TO_POSITION: dict[InstrumentTag, list[InstrumentPosition]] = dict()
    POSITION_TO_RANGE: dict[InstrumentPosition, tuple[Pitch, Octave, Stroke]] = dict()

    def __init__(self, run_settings: RunSettings) -> None:
        """Initializes lookup dicts and lists from settings files

        Args:
            instrumentgroup (InstrumentGroup): The type of orchestra (e.g. gong kebyar, semar pagulingan)
            version (Version):  Used to define which midi mapping to use from the midinotes.csv file.

        """
        self.SYMBOL_TO_NOTE.update(self.create_symbol_to_note_lookup(run_settings.font.filepath))
        self.NOTE_LIST.extend(list(self.SYMBOL_TO_NOTE.values()))
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
        midinotes_list = [note for notelist in self.INSTRUMENT_TO_MIDINOTE.values() for note in notelist]
        self.SYMBOLVALUE_TO_MIDINOTE.update(self.create_symbolvalue_to_midinote_lookup(midinotes_list))
        self.POSITION_TO_RANGE.update(self.create_position_range_lookup(midinotes_list))
        self.TAG_TO_POSITION.update(self.create_tag_to_position_lookup(run_settings.instruments))
        # TODO temporary solution in order to avoid circular imports. Is there a more elegant (less obscure) solution?
        # SilenceMeta.TAG_TO_POSITION_LOOKUP = TAG_TO_POSITION_LOOKUP
        MetaDataBaseType.TAG_TO_POSITION_LOOKUP = self.TAG_TO_POSITION

    def create_symbol_to_note_lookup(self, fromfile: str) -> dict[str, Note]:
        balifont_df = pd.read_csv(fromfile, sep="\t", quoting=csv.QUOTE_NONE)
        balifont_obj = balifont_df.where(pd.notnull(balifont_df), "NONE").to_dict(orient="records")
        balifont = [Note.model_validate(note_def) for note_def in balifont_obj]
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

    def create_symbolvalue_to_midinote_lookup(
        self,
        midinotes_list: list[MidiNote],
    ) -> dict[tuple[InstrumentPosition, Pitch, Octave, Stroke], MIDIvalue]:
        retval = {
            (position, midi.pitch, midi.octave, midi.stroke): midi
            for midi in midinotes_list
            for position in midi.positions
        }
        return retval

    def create_position_range_lookup(
        self,
        midinotes_list: list[MidiNote],
    ) -> dict[InstrumentPosition, list[tuple[Pitch, Octave, Stroke]]]:
        lookup = {
            position: [(midi.pitch, midi.octave, midi.stroke) for midi in midinotes_list if position in midi.positions]
            for position in InstrumentPosition
        }
        return lookup

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


run_settings = get_run_settings()
LOOKUP = Lookup(run_settings)
