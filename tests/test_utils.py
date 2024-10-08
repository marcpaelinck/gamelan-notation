import pytest

from src.common.classes import Beat, Gongan, Note
from src.common.constants import InstrumentPosition
from src.common.utils import (
    create_symbol_to_note_lookup,
    gongan_to_records,
    stave_to_string,
)
from src.notation2midi.notation_to_midi import passes_str_to_tuple
from src.settings.settings import InstrumentFields

BALIFONT5_TO_CHARACTER_DICT = create_symbol_to_note_lookup(fromfile="tests/data/balimusic5font.tsv")


def getchar(c: str) -> Note:
    return BALIFONT5_TO_CHARACTER_DICT[c]


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
                    sys_id=1,
                    bpm_start={},
                    bpm_end={},
                    duration=2,
                    staves={
                        instr: [getchar(c) for c in staves[idx]]
                        for instr, staves in {
                            InstrumentPosition.PEMADE_POLOS: ["a,a,", "oo", "ii", "ee", "oo", "ee", "ii", "oo"],
                            InstrumentPosition.PEMADE_SANGSIH: ["ee", "aa", "uu", "i<i<", "aa", "i<i<", "uu", "aa"],
                        }.items()
                    },
                )
                for idx in range(8)
            ],
        ),
        [
            {
                InstrumentFields.POSITION: InstrumentPosition.PEMADE_POLOS,
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
                InstrumentFields.POSITION: InstrumentPosition.PEMADE_SANGSIH,
                1: "ee",
                2: "aa",
                3: "uu",
                4: "i<i<",
                5: "aa",
                6: "i<i<",
                7: "uu",
                8: "aa",
            },
            {
                InstrumentFields.POSITION: "",
                1: "",
                2: "",
                3: "",
                4: "",
                5: "",
                6: "",
                7: "",
                8: "",
            },
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
    assert passes_str_to_tuple(rangestr) == expected


@pytest.mark.parametrize("rangestr", bad_ranges)
# Test that invalid values cause a ValueError to be raised
def test_range_str_to_list_exception(rangestr):
    with pytest.raises(ValueError):
        passes_str_to_tuple(rangestr)
