import csv

import pandas as pd
import pytest

from src.common.classes import Beat, Gongan, Measure, Note
from src.common.constants import DEFAULT, InstrumentType, Position
from src.notation2midi.score_to_notation import gongan_to_records, notelist_to_string
from src.settings.constants import InstrumentFields


def create_symbol_to_note_lookup(fromfile: str) -> dict[str, Note]:
    balifont_df = pd.read_csv(fromfile, sep="\t", quoting=csv.QUOTE_NONE)
    balifont_df.loc[balifont_df["duration"].isna(), "duration"] = 0
    balifont_df.loc[balifont_df["rest_after"].isna(), "rest_after"] = 0
    balifont_obj = balifont_df.where(pd.notnull(balifont_df), "NONE").to_dict(orient="records")
    balifont = [
        Note.model_validate(
            note_def
            | {
                "instrumenttype": InstrumentType.GENDERRAMBAT,
                "position": Position.GENDERRAMBAT,
            }
        )
        for note_def in balifont_obj
    ]
    return {note.symbol: note for note in balifont}


SYMBOL_TO_NOTE_LOOKUP = create_symbol_to_note_lookup(fromfile="./data/font/balimusic5font.tsv")

data1 = [
    ("iIoOeEuUaA", "iIoOeEuUaA"),
    ("io-eu-a8", "io-eu-a8"),
    ("i/o-e/u-a/i</", "i/o-e/u-a/i</"),
]


@pytest.mark.parametrize("chars, expected", data1)
def test_notelist_to_string(chars, expected):
    char_list = [SYMBOL_TO_NOTE_LOOKUP[c] for c in chars]
    assert notelist_to_string(char_list) == expected


data2 = [
    (
        Gongan(
            id=1,
            beats=[
                Beat(
                    id=idx + 1,
                    gongan_id=1,
                    bpm_start={},
                    bpm_end={},
                    velocities_start={},
                    velocities_end={},
                    duration=2,
                    measures={
                        instr: Measure(
                            position=instr,
                            passes={
                                DEFAULT: Measure.Pass(
                                    seq=DEFAULT,
                                    notes=[SYMBOL_TO_NOTE_LOOKUP[c] for c in notelists[idx]],
                                )
                            },
                        )
                        for instr, notelists in {
                            Position.PEMADE_POLOS: ["a,a,", "oo", "ii", "ee", "oo", "ee", "ii", "oo"],
                            Position.PEMADE_SANGSIH: ["ee", "aa", "uu", "i<i<", "aa", "i<i<", "uu", "aa"],
                        }.items()
                    },
                )
                for idx in range(8)
            ],
        ),
        [
            {
                InstrumentFields.POSITION: "PEMADE_P",
                1: "a,a,",
                2: "oo",
                3: "ii",
                4: "ee",
                5: "oo",
                6: "ee",
                7: "ii",
                8: "oo",
            },
            {
                InstrumentFields.POSITION: "PEMADE_S",
                1: "ee",
                2: "aa",
                3: "uu",
                4: "i<i<",
                5: "aa",
                6: "i<i<",
                7: "uu",
                8: "aa",
            },
            {InstrumentFields.POSITION: "", 1: "", 2: "", 3: "", 4: "", 5: "", 6: "", 7: "", 8: ""},
        ],
    )
]


@pytest.mark.parametrize("gongan, expected", data2)
def test_gongan_to_records(gongan, expected):
    assert gongan_to_records(gongan) == expected
