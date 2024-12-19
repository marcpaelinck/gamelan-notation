from enum import Enum

import pandas as pd
from pydantic import BaseModel

from src.common.constants import (
    InstrumentGroup,
    InstrumentType,
    Modifier,
    Pitch,
    Position,
    Stroke,
)
from src.settings.classes import InstrumentRecord, InstrumentTagRecord
from src.settings.constants import InstrumentFields, InstrumentTagFields, SStrEnum

# Target types for all column headers used in the settings files
TYPES = {
    "balifont_symbol_description": str,
    "bank": int,
    "channel": int,
    "description": str,
    "duration": float,
    "group": InstrumentGroup,
    "instrumentgroup": InstrumentGroup,
    "infile": str,
    "instrument": InstrumentType,
    "instrumenttype": InstrumentType,
    "midinote": int,
    "modifier": Modifier,
    "octave": int,
    "pitch": Pitch,
    "position": Position,
    "positions": Position,
    "preset": int,
    "preset_name": str,
    "remark": str,
    "rest_after": float,
    "rootnote": str,
    "sample": str,
    "stroke": Stroke,
    "symbol": str,
    "symbol_description": str,
    "tag": str,
    "unicode": str,
}


# Functions that should be applied to each field when processing the MIDI data
def formatter(element_type: type):
    locals = {"": "x"} | {x.value: x for x in element_type} if issubclass(element_type, Enum) else None
    return lambda x: ((eval(x, globals(), locals) if locals else eval(x)) if x.startswith("[") else element_type(x))


DTYPES = {int: "int64", float: "float64"}


def get_formatters(fields: SStrEnum) -> dict[str, callable]:
    return {field: formatter(TYPES.get(field, str)) for field in fields}


def get_dtypes(fields: Enum) -> dict[str, str]:
    return {field: DTYPES[TYPES[field]] for field in fields if DTYPES.get(TYPES[field], None)}


def read_table(filepath: str, fields: Enum, outtype: BaseModel) -> list[InstrumentRecord]:
    formatters = get_formatters(fields)
    dtypes = get_dtypes(fields)

    dict_list = pd.read_csv(filepath, sep="\t", comment="#", dtype=dtypes, converters=formatters).to_dict(
        orient="records"
    )
    return [outtype.model_validate(record) for record in dict_list]


if __name__ == "__main__":
    # instr = read_table("./data/instruments/instruments.tsv", InstrumentFields, InstrumentRecord)
    instr = read_table("./data/midi/gamelan_midinotes1.tsv", InstrumentTagFields, InstrumentTagRecord)
    print(locals())
    # print(eval())
    x = 1
