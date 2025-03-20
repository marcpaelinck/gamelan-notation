"""Validates the definitions in the settings folder"""

import csv

import pandas as pd

from src.common.constants import Pitch
from src.common.logger import get_logger
from src.notation2midi.classes import ParserModel
from src.settings.constants import FontFields, MidiNotesFields

logger = get_logger(__name__)


class SettingsValidator(ParserModel):
    """Validates the definition files in the settings folder."""

    def __init__(self, run_settings: dict):
        super().__init__(ParserModel.ParserType.SETTINGSVALIDATOR, run_settings)

    def _check_unique_character_values(self) -> None:
        """Analyzes the font definition setting and detects characters that have the same
        values for fields `value`, `duration` and `rest_after`.
        """
        groupby = [FontFields.PITCH, FontFields.OCTAVE, FontFields.STROKE, FontFields.DURATION, FontFields.REST_AFTER]
        font_df = pd.read_csv(self.run_settings.configdata.font.filepath, sep="\t", quoting=csv.QUOTE_NONE)[
            groupby + [FontFields.SYMBOL]
        ]
        duplicates = font_df[font_df.duplicated(groupby, keep=False)].groupby(groupby)[FontFields.SYMBOL].apply(list)
        if duplicates.size > 0:
            logger.warning("DUPLICATE CHARACTER VALUES:")
            logger.warning(duplicates)
        else:
            logger.info("NO DUPLICATE CHARACTER VALUES FOUND.")

    def _check_font_midi_match(self) -> None:
        """Checks the consistency of the font definition settings file and the midi settings file.
        Reports if any value in one file has no match in the other one.
        """
        font_keys = [FontFields.PITCH, FontFields.OCTAVE, FontFields.STROKE]
        midi_keys = [MidiNotesFields.PITCH, MidiNotesFields.OCTAVE, MidiNotesFields.STROKE]
        midi_keep = midi_keys + [MidiNotesFields.INSTRUMENTTYPE, MidiNotesFields.POSITIONS]
        instrumentgroup = self.run_settings.instrumentgroup

        # 1. Find midi notes without corresponding character definition.
        # Use Int64 type to cope with NaN values,
        # see https://pandas.pydata.org/pandas-docs/version/0.24/whatsnew/v0.24.0.html#optional-integer-na-support
        font_df = pd.read_csv(
            self.run_settings.configdata.font.filepath,
            sep="\t",
            quoting=csv.QUOTE_NONE,
            dtype={FontFields.OCTAVE: "Int64"},
        )[font_keys]
        midi_df = pd.read_csv(
            self.run_settings.midi.notes_filepath, sep="\t", quoting=csv.QUOTE_NONE, dtype={FontFields.OCTAVE: "Int64"}
        )
        midi_values = (
            midi_df[midi_df[MidiNotesFields.INSTRUMENTGROUP] == instrumentgroup]
            .drop([MidiNotesFields.INSTRUMENTGROUP], axis="columns")
            .drop_duplicates()
        )[midi_keep]
        merged = midi_values.merge(
            font_df, how="left", left_on=(midi_keys), right_on=(font_keys), suffixes=["_F", "_M"]
        )
        missing = merged[merged[FontFields.PITCH].isna()]
        if missing.size > 0:
            logger.warning("MIDI NOTES MISSING A CHARACTER EQUIVALENT IN THE FONT DEFINITION FOR %s:", instrumentgroup)
            logger.warning(missing[midi_keys].drop_duplicates())
        else:
            logger.info("ALL MIDI NOTES HAVE A CORRESPONDING CHARACTER IN THE FONT DEFINITION FOR %s.", instrumentgroup)

        # 2. Find notes without corresponding midi value.
        merged = font_df.merge(
            midi_values, how="left", left_on=(font_keys), right_on=(midi_keys), suffixes=["_F", "_M"]
        )
        missing = merged[merged[MidiNotesFields.PITCH].isna() & ~(merged[FontFields.PITCH] == Pitch.NONE.value)]
        if missing.size > 0:
            logger.info("-------------------------------------")
            logger.warning("CHARACTERS IN THE FONT DEFINITION MISSING A MIDI NOTE EQUIVALENT FOR %s:", instrumentgroup)
            logger.warning(missing[font_keys].drop_duplicates())
        else:
            logger.info("ALL CHARACTERS HAVE A CORRESPONDING NOTE IN THE MIDINOTES DEFINITION FOR %s.", instrumentgroup)

    @ParserModel.main
    def validate_input_data(self):
        """Main method which performs the validation."""
        self._check_unique_character_values()
        logger.info("-------------------------------------")
        self._check_font_midi_match()
