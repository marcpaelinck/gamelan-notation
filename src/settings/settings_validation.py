"""Validates the definitions in the settings folder"""

import csv
from typing import override

import pandas as pd

from src.common.constants import ModifierType, Pitch, Stroke
from src.common.logger import Logging
from src.notation2midi.classes import Agent
from src.settings.classes import RunSettings
from src.settings.constants import FontFields, MidiNotesFields, ModifiersFields

logger = Logging.get_logger(__name__)


class SettingsValidationAgent(Agent):
    """Validates the definition files in the settings folder."""

    LOGGING_MESSAGE = "VALIDATING RUN SETTINGS"
    EXPECTED_INPUT_TYPES = (Agent.InputOutputType.RUNSETTINGS,)
    RETURN_TYPE = None

    @override
    @classmethod
    def run_condition_satisfied(cls, run_settings: RunSettings):
        return True

    def _check_unique_character_values(self) -> None:
        """Analyzes the font definition setting and detects characters that have the same
        values for fields `pitch` and `modifier`.
        """
        groupby = [FontFields.PITCH, FontFields.MODIFIER]
        font_df = pd.read_csv(self.run_settings.configdata.font.filepath, sep="\t", quoting=csv.QUOTE_NONE)[
            groupby + [FontFields.SYMBOL]
        ]
        duplicates = font_df[font_df.duplicated(groupby, keep=False)].groupby(groupby)[FontFields.SYMBOL].apply(list)
        if duplicates.size > 0:
            self.logwarning("DUPLICATE CHARACTER VALUES:")
            self.logwarning(duplicates)
        else:
            self.loginfo("NO DUPLICATE CHARACTER VALUES FOUND.")

    def _check_font_midi_match(self) -> None:
        """Checks the consistency of the font definition settings file and the midi settings file.
        Reports if any value in one file has no match in the other one.
        """
        font_keys = [FontFields.PITCH, FontFields.OCTAVE, FontFields.MODIFIER]
        midi_keys = [MidiNotesFields.PITCH, MidiNotesFields.OCTAVE, MidiNotesFields.STROKE]
        midi_keep = midi_keys + [
            MidiNotesFields.INSTRUMENTTYPE,
            MidiNotesFields.POSITIONS,
            MidiNotesFields.GROUP,
        ]
        instrumentgroup = self.run_settings.instrumentgroup

        # 1. Find midi notes without corresponding character definition.
        # Use Int64 type to cope with NaN values,
        # see https://pandas.pydata.org/pandas-docs/version/0.24/whatsnew/v0.24.0.html#optional-integer-na-support
        #
        # First combine the font and modifiers tables
        font_df = pd.DataFrame.from_records(self.run_settings.data.font)[font_keys]
        mod_dict = {
            modtype: {
                mod[ModifiersFields.MODIFIER]: mod[ModifiersFields.VALUE]
                for mod in self.run_settings.data.modifiers
                if mod[ModifiersFields.MOD_TYPE] is modtype
            }
            for modtype in [ModifierType.STROKE, ModifierType.OCTAVE]
        }
        font_df[MidiNotesFields.STROKE] = font_df[FontFields.MODIFIER].apply(
            lambda x: mod_dict[ModifierType.STROKE].get(x, Stroke.OPEN)
        )
        font_df[MidiNotesFields.OCTAVE] = font_df[[FontFields.MODIFIER, FontFields.OCTAVE]].apply(
            lambda x: mod_dict[ModifierType.OCTAVE].get(x[FontFields.MODIFIER], x[FontFields.OCTAVE]), axis=1
        )
        midi_df = pd.DataFrame.from_records(self.run_settings.data.midinotes)[midi_keep]
        # Convert lists to tuples in order to discard duplicates
        midi_df[MidiNotesFields.POSITIONS] = midi_df[MidiNotesFields.POSITIONS].apply(lambda x: tuple(x))
        midi_values = (
            midi_df[midi_df[MidiNotesFields.GROUP] == instrumentgroup]
            .drop([MidiNotesFields.GROUP], axis="columns")
            .drop_duplicates()
        )
        merged = midi_values.merge(
            font_df, how="left", left_on=(midi_keys), right_on=(font_keys), suffixes=["_F", "_M"]
        )
        missing = merged[merged[FontFields.PITCH].isna()]
        if missing.size > 0:
            self.logwarning("MIDI NOTES MISSING A CHARACTER EQUIVALENT IN THE FONT DEFINITION FOR %s:", instrumentgroup)
            self.logwarning(missing[midi_keys].drop_duplicates())
        else:
            self.loginfo(
                "ALL MIDI NOTES HAVE A CORRESPONDING CHARACTER IN THE FONT DEFINITION FOR %s.", instrumentgroup
            )

        # 2. Find notes without corresponding midi value.
        merged = font_df.merge(
            midi_values, how="left", left_on=(font_keys), right_on=(midi_keys), suffixes=["_F", "_M"]
        )
        missing = merged[merged[MidiNotesFields.PITCH].isna() & ~(merged[FontFields.PITCH] == Pitch.NONE.value)]
        if missing.size > 0:
            self.loginfo("")
            self.logwarning("CHARACTERS IN THE FONT DEFINITION MISSING A MIDI NOTE EQUIVALENT FOR %s:", instrumentgroup)
            self.logwarning(missing[font_keys].drop_duplicates())
        else:
            self.loginfo(
                "ALL CHARACTERS HAVE A CORRESPONDING NOTE IN THE MIDINOTES DEFINITION FOR %s.", instrumentgroup
            )

    @override
    def _main(self):
        """Main method which performs the validation."""
        self.loginfo(f"Instrument group: {self.run_settings.instrumentgroup.value}")
        self._check_unique_character_values()
        self._check_font_midi_match()
