import csv

import pandas as pd
import pytest

from src.common.classes import Beat, Gongan, Note, Score
from src.common.constants import Position
from src.common.utils import gongan_to_records, stave_to_string
from src.notation2midi.notation5_to_dict import Font5Parser
from src.settings.settings import InstrumentFields, get_run_settings


def create_symbol_to_note_lookup(fromfile: str) -> dict[str, Note]:
    balifont_df = pd.read_csv(fromfile, sep="\t", quoting=csv.QUOTE_NONE)
    balifont_obj = balifont_df.where(pd.notnull(balifont_df), "NONE").to_dict(orient="records")
    balifont = [
        Note.model_validate(note_def | {"position": Position.GENDERRAMBAT, "_validate_range": False})
        for note_def in balifont_obj
    ]
    return {note.symbol: note for note in balifont}


BALIFONT5_TO_NOTE_DICT = create_symbol_to_note_lookup(fromfile="tests/data/balimusic5font.tsv")


def getchar(c: str) -> Note:
    return BALIFONT5_TO_NOTE_DICT[c]


data1 = [
    ([getchar(c) for c in "iIoOeEuUaA"], "iIoOeEuUaA"),
    ([getchar(c) for c in "io-eu-a8"], "io-eu-a8"),
    ([getchar(c) for c in "i/o-e/u-a/i</"], "i/o-e/u-a/i</"),
]


@pytest.mark.parametrize("char_list, expected", data1)
def test_stave_to_string(char_list, expected):
    assert stave_to_string(char_list) == expected


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
                    staves={
                        instr: [getchar(c) for c in staves[idx]]
                        for instr, staves in {
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


# Tests for range_str_to_list

correct_ranges = [
    ("1", [1]),
    ("1-3", [1, 2, 3]),
    ("3-4", [3, 4]),
    ("3,4", [3, 4]),
]

bad_ranges = ["1,2,", "realbad", "1-", "-1", "-", ",", "1-4-"]


@pytest.mark.parametrize("rangestr, expected", correct_ranges)
# Tests the conversion of optional range indicators following the position name in the score
def test_range_str_to_list(rangestr, expected):
    run_settings = get_run_settings()
    parser = Font5Parser(run_settings=run_settings)
    assert parser._passes_str_to_list(rangestr) == expected


@pytest.mark.parametrize("rangestr", bad_ranges)
# Test that invalid values cause a ValueError to be raised
def test_range_str_to_list_exception(rangestr):
    with pytest.raises(ValueError):
        run_settings = get_run_settings()
        parser = Font5Parser(run_settings=run_settings)
        parser._passes_str_to_list(rangestr)
