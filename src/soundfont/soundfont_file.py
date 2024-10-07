import os
from functools import partial

import pandas as pd
from openpyxl.styles import Font, PatternFill
from openpyxl.workbook.workbook import Workbook
from openpyxl.worksheet.worksheet import Worksheet

from src.common.classes import RunSettings
from src.common.constants import InstrumentType
from src.notation2midi.settings import get_run_settings

MidiDict = list[dict[str, str | int | None]]
BOLD = Font(bold=True)


class Sheet:
    sheet: Worksheet = None

    def __init__(self, sheet: Worksheet):
        self.sheet = sheet

    def isempty(self) -> bool:
        return [row for row in self.sheet.rows] == []

    def next_empty_row_nbr(self):
        return 1 if self.isempty() else self.sheet.max_row + 1

    def add_row(self, titles: list[str], bold: bool | list[bool] = False) -> None:
        row = self.next_empty_row_nbr()
        for col, title in enumerate(titles):
            self.sheet.cell(row=row, column=col + 1).value = title
            if (isinstance(bold, bool) and bold) or (isinstance(bold, list) and bold[col]):
                self.sheet.cell(row=row, column=col + 1).font = BOLD

    def add_separator(self) -> None:
        row = self.next_empty_row_nbr()
        for col in range(1, 8):
            self.sheet.cell(row, col).fill = PatternFill(fill_type="mediumGray")


def add_sample_section(sheet: Sheet, midi_dict: MidiDict, settings: RunSettings) -> None:
    # Add title row
    sheet.add_row(["Samples", "Name", "Loop S-E", "Root key", "Correction", "File name", "Folder"], bold=True)
    for record in midi_dict:
        sheet.add_row(["", record["sample_name"], "", record["midinote"], "", record["sample"]])
    sheet.add_row(["Search paths:", os.path.abspath(settings.samples.folder)], bold=[True, False])
    sheet.add_separator()


def add_instrument_section(sheet: Sheet, midi_dict: MidiDict) -> None:
    sheet.add_row(["Instruments", "Name", "Generators"], bold=True)
    midi_dict_grouped = {
        instr: [record for record in midi_dict if record["instrumenttype"] == instr]
        for instr in {record["instrumenttype"] for record in midi_dict}
    }
    for instrumenttype, records in midi_dict_grouped.items():
        sheet.add_row(["", instrumenttype])
        bolds = [False, False, True] + ([False] * len(records))
        sheet.add_row(
            ["", "", "Sample name"] + [record["sample_name"] for record in records],
            bold=bolds
        )
        sheet.add_row(
            ["", "", "Key Range"] + [f"{record["midinote"]}-{record["midinote"]}" for record in records],
           bold=bolds
        )
        sheet.add_row(
            ["", "", "Root Key"] + [record["midinote"] for record in records],
           bold=bolds
        )
    sheet.add_separator()


def add_preset_section(sheet: Worksheet, preset_dict: MidiDict) -> None: ...


def get_midi_dict(settings: RunSettings) -> MidiDict:
    midi_df = pd.read_csv(settings.midi.notes_filepath, sep="\t", dtype={"octave": "Int64", "midinote": "Int64"})
    midi_dict = (
        midi_df[(midi_df["instrumentgroup"] == settings.instruments.instrumentgroup) & pd.notnull(midi_df["sample"])]
        .sort_values(by=["midinote", "stroke", "instrumenttype"], ascending=[True, False, True])
        .drop(["instrumentgroup", "remark", "positions"], axis="columns")
        .drop_duplicates("midinote")
        .to_dict(orient="records")
    )
    for record in midi_dict:
        record["sample_name"] = (
            record["instrumenttype"] + " " + record["pitch"] + str(record["octave"] or "") + " " + record["stroke"]
        )
    return midi_dict


def get_preset_dict(settings: RunSettings) -> list[dict[str, str | int | None]]:
    def sortkey(value: pd.Series):
        match value.name:
            case "instrumenttype":
                return value.apply(lambda val: InstrumentType[val].sequence)
            case _:
                return value

    to_records = partial(pd.DataFrame.to_dict, orient="records")
    preset_df = pd.read_csv(settings.midi.presets_filepath, sep="\t")
    preset_dict = (
        preset_df[preset_df["instrumentgroup"] == settings.instruments.instrumentgroup]
        .sort_values(by=["bank", "preset", "instrumenttype"], key=sortkey)
        .drop(["instrumentgroup"], axis="columns")
        # .groupby("instrumenttype")[["bank", "preset", "preset_name"]]
        # .apply(to_records)
        .to_dict(orient="records")
    )
    return preset_dict


def create_soundfont_file():
    run_settings = get_run_settings()
    midi_dict = get_midi_dict(run_settings)
    preset_dict = get_preset_dict(run_settings)
    workbook = Workbook()
    workbook.active.title = "Viena definition"
    sheet = Sheet(workbook.active)
    add_sample_section(sheet, midi_dict, run_settings)
    add_instrument_section(sheet, midi_dict)
    add_preset_section(sheet, preset_dict)
    workbook.save("./data/soundfont/viena_definition.xlsx")


if __name__ == "__main__":
    create_soundfont_file()
