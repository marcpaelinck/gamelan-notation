import pytest

from src.common.classes import Beat, Character, System
from src.common.constants import InstrumentPosition
from src.common.utils import (
    create_symbol_to_character_lookup,
    stave_to_string,
    system_to_records,
)
from src.notation2midi.settings import InstrumentFields

BALIFONT4_TO_CHARACTER_DICT = create_symbol_to_character_lookup(fromfile="tests/data/balimusic4font.csv")
BALIFONT4_TO_CHARACTER_DICT = create_symbol_to_character_lookup(fromfile="tests/data/balimusic4font.csv")


def getchar(c: str) -> Character:
    return BALIFONT4_TO_CHARACTER_DICT[c]


data1 = [
    ([getchar(c) for c in "iIoOeEuUaA"], "iIoOeEuUaA"),
    ([getchar(c) for c in "i^o-e^u-a^8"], "i^o-e^u-a^8"),
    ([getchar(c) for c in "i/o-e/u-a/8"], "i/o-e/u-a/8"),
]


@pytest.mark.parametrize("char_list, expected", data1)
def test_stave_to_string(char_list, expected):
    assert stave_to_string(char_list) == expected


data2 = [
    (
        System(
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
                            InstrumentPosition.PEMADE_POLOS: ["zz", "oo", "ii", "ee", "oo", "ee", "ii", "oo"],
                            InstrumentPosition.PEMADE_SANGSIH: ["ee", "aa", "uu", "88", "aa", "88", "uu", "aa"],
                        }.items()
                    },
                )
                for idx in range(8)
            ],
        ),
        [
            {
                InstrumentFields.POSITION: InstrumentPosition.PEMADE_POLOS,
                1: "zz",
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
                4: "88",
                5: "aa",
                6: "88",
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


@pytest.mark.parametrize("system, expected", data2)
def test_system_to_records(system, expected):
    assert system_to_records(system) == expected
