""" Creates an Excel soundfont definition file. This file can imported in the Viena application 
    to create a  Soundfont file (.sf2 format). See http://www.synthfont.com/The_Definitions_File.pdf

    Main method: create_soundfont_file()
"""

from functools import partial

import pandas as pd

from src.common.classes import RunSettings
from src.common.constants import InstrumentType, MidiDict
from src.settings.settings import get_run_settings
from src.settings.settings_validation import validate_settings
from src.soundfont.soundfont_textfile import SoundfontTextfile
from src.soundfont.soundfont_workbook import SoundfontWorkbook


def create_sample_name(instrumenttype: str, pitch: int, octave: int | None, stroke: str) -> str:
    """Creates a name for the sample / midi note, based on the given values.
    Names longer than 20 characters are truncated.

    Args:
        instrumenttype (str): _description_
        pitch (int): _description_
        octave (int | None): _description_
        stroke (str): _description_

    Returns:
        str: _description_
    """
    MAXLENGTH = 20
    octave_str = str(octave) if octave is not None else ""
    components = [instrumenttype, " ", pitch, octave_str, " ", stroke]
    surplus = max(sum(len(part) for part in components) - MAXLENGTH, 0)
    # truncate the longest components of the name if MAXLENGTH is exceeded.
    for _ in range(surplus):
        # find the longest component and remove its last character
        idx = components.index(max(components, key=len))
        components[idx] = components[idx][:-1]
    return "".join(components)


def get_midi_dict(settings: RunSettings) -> MidiDict:
    """Reads the midinotes table and converts it into a dict of the form:
        {<instrumenttype>: [<record>, <record>, ...]}
    where <record> has the form
        {"instrumenttype": <value>, "pitch": <value>, "octave": <value>, "stroke": <value>, "midinote": <value>, "sample": <value>}

    Args:
        settings (RunSettings): used to retrieve the file path and required instrument group

    Returns:
        MidiDict:
    """
    midi_df = pd.read_csv(settings.midi.notes_filepath, sep="\t", dtype={"octave": "Int64", "midinote": "Int64"})
    to_records = partial(pd.DataFrame.to_dict, orient="records")
    midi_dict = (
        midi_df[(midi_df["instrumentgroup"] == settings.instruments.instrumentgroup) & pd.notnull(midi_df["sample"])]
        .sort_values(by=["midinote", "stroke", "instrumenttype"], ascending=[True, False, True])
        .drop(["instrumentgroup", "remark", "positions"], axis="columns")
        # .drop_duplicates("midinote") removed: the same midi note number can occur in multiple banks / presets
        .groupby(["instrumenttype"])[["instrumenttype", "pitch", "octave", "stroke", "midinote", "sample"]]
        .apply(to_records)
        .to_dict()
    )
    for instrumenttype, records in midi_dict.items():
        for record in records:
            record["sample_name"] = create_sample_name(
                instrumenttype, record["pitch"], record["octave"], record["stroke"]
            )
    return midi_dict


def get_preset_dict(settings: RunSettings, instruments: list[InstrumentType]) -> MidiDict:
    """Reads the presets table and converts it into a dict of the form:
        {(<preset_name>, <bank>, <preset>): [<record>, <record>, ...]}
    where <record> has the form
        {"instrumenttype": <value>, "instrumentgroup": <value>}

    Args:
        settings (RunSettings): used to retrieve the file path and required instrument group

    Returns:
        MidiDict:
    """

    def sortkey(value: pd.Series):
        if value.name == "instrumenttype":
            return value.apply(lambda val: InstrumentType[val].sequence)
        else:
            return value

    to_records = partial(pd.DataFrame.to_dict, orient="records")
    preset_df = pd.read_csv(settings.midi.presets_filepath, sep="\t")
    preset_dict = (
        preset_df[
            (preset_df["instrumentgroup"] == settings.instruments.instrumentgroup)
            & preset_df["instrumenttype"].isin(instruments)
        ]
        .sort_values(by=["bank", "preset", "instrumenttype"], key=sortkey)
        .groupby(["preset_name", "bank", "preset"])[["instrumenttype", "instrumentgroup"]]
        .apply(to_records)
        .to_dict()
    )
    return preset_dict


def create_soundfont_file():
    """This method does all the work.
    All settings are read from the (YAML) settings files.
    """
    run_settings = get_run_settings()
    if run_settings.switches.validate_settings:
        validate_settings(run_settings)

    midi_dict = get_midi_dict(run_settings)
    preset_dict = get_preset_dict(run_settings, midi_dict.keys())

    # workbook = SoundfontWorkbook(midi_dict=midi_dict, preset_dict=preset_dict, settings=run_settings)
    workbook = SoundfontTextfile(midi_dict=midi_dict, preset_dict=preset_dict, settings=run_settings)
    workbook.create_soundfont_definition()
    workbook.save()


if __name__ == "__main__":
    create_soundfont_file()
