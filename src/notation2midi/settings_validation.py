""" Validates the definitions in the settings folder
"""

import csv

import numpy as np
import pandas as pd

from src.common.classes import Source
from src.common.constants import InstrumentGroup, Note
from src.notation2midi.settings import (
    MIDI_NOTES_DEF_FILE,
    NOTATIONFONT_DEF_FILES,
    FontFields,
    MidiNotesFields,
)


def check_unique_character_values(source: Source) -> None:
    """Analyzes the font definition setting and detects characters that have the same
    values for fields `value`, `duration` and `rest_after`.
    """
    groupby = [FontFields.NOTE, FontFields.OCTAVE, FontFields.STROKE, FontFields.DURATION, FontFields.REST_AFTER]
    font_df = pd.read_csv(NOTATIONFONT_DEF_FILES[source.font], sep="\t", quoting=csv.QUOTE_NONE)[
        groupby + [FontFields.SYMBOL]
    ]
    duplicates = font_df[font_df.duplicated(groupby, keep=False)].groupby(groupby)[FontFields.SYMBOL].apply(list)
    if duplicates.size > 0:
        print("DUPLICATE CHARACTER VALUES:")
        print(duplicates)
    else:
        print("NO DUPLICATE CHARACTER VALUES FOUND.")


def check_font_midi_match(source: Source) -> None:
    """Checks the consistency of the font definition settings file and the midi settings file.
    Reports if any value in one file has no match in the other one.
    """
    font_keys = [FontFields.NOTE, FontFields.OCTAVE, FontFields.STROKE]
    midi_keys = [MidiNotesFields.NOTE, MidiNotesFields.OCTAVE, MidiNotesFields.STROKE]
    midi_keep = midi_keys + [MidiNotesFields.INSTRUMENTTYPE, MidiNotesFields.POSITIONS]

    # 1. Find midi notes without corresponding character definition.
    # Use Int64 type to cope with NaN values,
    # see https://pandas.pydata.org/pandas-docs/version/0.24/whatsnew/v0.24.0.html#optional-integer-na-support
    font_df = pd.read_csv(
        NOTATIONFONT_DEF_FILES[source.font], sep="\t", quoting=csv.QUOTE_NONE, dtype={FontFields.OCTAVE: "Int64"}
    )[font_keys]
    midi_df = pd.read_csv(MIDI_NOTES_DEF_FILE, sep="\t", quoting=csv.QUOTE_NONE, dtype={FontFields.OCTAVE: "Int64"})
    midi_values = (
        midi_df[midi_df[MidiNotesFields.INSTRUMENTGROUP] == source.instrumentgroup]
        .drop([MidiNotesFields.INSTRUMENTGROUP], axis="columns")
        .drop_duplicates()
    )[midi_keep]
    merged = midi_values.merge(font_df, how="left", left_on=(midi_keys), right_on=(font_keys), suffixes=["_F", "_M"])
    missing = merged[merged[FontFields.NOTE].isna()]
    if missing.size > 0:
        print(f"MIDI NOTES MISSING A CHARACTER EQUIVALENT IN THE FONT DEFINITION FOR {source.instrumentgroup}:")
        print(missing[midi_keys].drop_duplicates())
    else:
        print(f"ALL MIDI NOTES HAVE A CORRESPONDING CHARACTER IN THE FONT DEFINITION FOR {source.instrumentgroup}.")

    # 2. Find characters without corresponding midi note.
    merged = font_df.merge(midi_values, how="left", left_on=(font_keys), right_on=(midi_keys), suffixes=["_F", "_M"])
    missing = merged[merged[MidiNotesFields.NOTE].isna() & ~(merged[FontFields.NOTE] == Note.NONE.value)]
    if missing.size > 0:
        print("-------------------------------------")
        print(f"CHARACTERS IN THE FONT DEFINITION MISSING A MIDI NOTE EQUIVALENT FOR {source.instrumentgroup}:")
        print(missing[font_keys].drop_duplicates())
    else:
        print(f"ALL CHARACTERS HAVE A CORRESPONDING NOTE IN THE MIDINOTES DEFINITION FOR {source.instrumentgroup}.")


def validate_settings(source: Source):
    print("======== SETTINGS VALIDATION ========")
    check_unique_character_values(source)
    print("-------------------------------------")
    check_font_midi_match(source)
    print("=====================================")
