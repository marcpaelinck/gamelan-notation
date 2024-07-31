import pytest

from src.notation_classes import Beat, Character, System
from src.notation_constants import InstrumentPosition
from src.settings import InstrumentFields
from src.utils import create_balimusic4_font_lookup, stave_to_string, system_to_records

BALIFONT4_TO_CHARACTER_DICT = create_balimusic4_font_lookup(fromfile="tests/data/balimusic4font.csv")


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
        ],
    )
]


@pytest.mark.parametrize("system, expected", data2)
def test_system_to_records(system, expected):
    assert system_to_records(system) == expected
