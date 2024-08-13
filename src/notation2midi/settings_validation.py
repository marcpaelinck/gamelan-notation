""" Validates the definitions in the settings folder
"""

import csv

import pandas as pd

from src.common.constants import InstrumentGroup, SymbolValue
from src.notation2midi.settings import (
    MIDI_NOTES_DEF_FILE,
    NOTATIONFONT_DEF_FILE,
    FontFields,
    MidiNotesFields,
)


def check_unique_character_values() -> None:
    """Analyzes the font definition setting and detects characters that have the same
    values for fields `value`, `duration` and `rest_after`.
    """
    groupby = [FontFields.SYMBOLVALUE, FontFields.DURATION, FontFields.REST_AFTER]
    font_df = pd.read_csv(NOTATIONFONT_DEF_FILE, sep="\t", quoting=csv.QUOTE_NONE)[groupby + [FontFields.SYMBOL]]
    duplicates = (
        font_df[font_df.duplicated([FontFields.SYMBOLVALUE, FontFields.DURATION, FontFields.REST_AFTER], keep=False)]
        .groupby(groupby)[FontFields.SYMBOL]
        .apply(list)
    )
    if duplicates.size > 0:
        print("DUPLICATE CHARACTER VALUES:")
        print(duplicates)
    else:
        print("NO DUPLICATE CHARACTER VALUES FOUND.")


def check_font_midi_match(group: InstrumentGroup) -> None:
    """Checks the consistency of the font definition settings file and the midi settings file.
    Reports if any value in one file has no match in the other one.
    """
    # 1. Find midi notes without corresponding character definition.
    font_keep = [FontFields.SYMBOLVALUE]
    midi_keep = [
        MidiNotesFields.INSTRUMENTGROUP,
        MidiNotesFields.INSTRUMENTTYPE,
        MidiNotesFields.POSITIONS,
        MidiNotesFields.SYMBOLVALUE,
    ]
    font_df = pd.read_csv(NOTATIONFONT_DEF_FILE, sep="\t", quoting=csv.QUOTE_NONE)[font_keep]
    midi_df = pd.read_csv(MIDI_NOTES_DEF_FILE, sep="\t", quoting=csv.QUOTE_NONE)[midi_keep]
    midi_values = (
        midi_df[midi_df[MidiNotesFields.INSTRUMENTGROUP] == group]
        .drop([MidiNotesFields.INSTRUMENTGROUP], axis="columns")
        .drop_duplicates()
    )
    merged = midi_values.merge(
        font_df, how="left", left_on=MidiNotesFields.SYMBOLVALUE, right_on=FontFields.SYMBOLVALUE, suffixes=["_F", "_M"]
    )
    missing = merged[merged[FontFields.SYMBOLVALUE].isna()].drop(FontFields.SYMBOLVALUE, axis="columns")
    if missing.size > 0:
        print(f"CHARACTERS IN THE FONT DEFINITION MISSING A MIDI NOTE EQUIVALENT FOR {group}:")
        print(missing)
    else:
        print("ALL CHARACTERS HAVE A CORRESPONDING NOTE IN THE MIDINOTES DEFINITION FOR {group}.")

    # 2. Find characters without corresponding midi note.
    non_notes = [symvalue.value for symvalue in SymbolValue if not symvalue.isnote]
    merged = font_df.merge(
        midi_values,
        how="left",
        left_on=FontFields.SYMBOLVALUE,
        right_on=MidiNotesFields.SYMBOLVALUE,
        suffixes=["_F", "_M"],
    )
    missing = merged[merged[MidiNotesFields.SYMBOLVALUE].isna() & ~merged[FontFields.SYMBOLVALUE].isin(non_notes)]
    if missing.size > 0:
        print("-------------------------------------")
        print("MIDI NOTES MISSING A CHARACTER EQUIVALENT IN THE FONT DEFINITION FOR {group}:")
        print(missing[FontFields.SYMBOLVALUE].drop_duplicates())
    else:
        print("ALL MIDI NOTES HAVE A CORRESPONDING CHARACTER IN THE FONT DEFINITION FOR {group}.")


def validate_settings(group: InstrumentGroup):
    print("======== SETTINGS VALIDATION ========")
    check_unique_character_values()
    print("-------------------------------------")
    check_font_midi_match(group)
    print("=====================================")


if __name__ == "__main__":
    validate_settings(group=InstrumentGroup.GONG_KEBYAR)
