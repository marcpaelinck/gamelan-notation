import unittest
from itertools import product
from unittest.mock import patch

import pytest

import src.settings.settings
from src.common.classes import Instrument, Note, Tone
from src.common.constants import (
    Pitch,
    Position,
    RuleParameter,
    RuleType,
    RuleValue,
    Stroke,
)
from src.settings.constants import Yaml


@patch("src.settings.settings.SETTINGSFOLDER", "./tests/settings")
def load_settings_sp():
    # Create mock notation and converter for semar pagulingan score
    src.settings.settings.load_run_settings(notation={Yaml.COMPOSITION: "test-semarpagulingan", Yaml.PART_ID: "full"})


@patch("src.settings.settings.SETTINGSFOLDER", "./tests/settings")
def load_settings_gk():
    # Create mock notation and converter for gong kebyar score with beat at end
    src.settings.settings.load_run_settings(notation={Yaml.COMPOSITION: "test-gongkebyar", Yaml.PART_ID: "full"})


tone_range_data = [
    (
        Tone(Pitch.DONG, octave=1),
        Position.PEMADE_POLOS,
        (
            [Tone(Pitch.DONG, octave=1)],  # extended_range==True, exact_match==True
            [Tone(Pitch.DONG, octave=1), Tone(Pitch.DONG, octave=0)],  # extended_range==True, exact_match==False
            [Tone(Pitch.DONG, octave=1)],  # extended_range==False, exact_match==True
            [Tone(Pitch.DONG, octave=1), Tone(Pitch.DONG, octave=0)],  # extended_range==False, exact_match==False
        ),
    ),
    (
        Tone(Pitch.DONG, octave=2),
        Position.REYONG_2,
        (
            [],
            [Tone(Pitch.DONG, octave=1)],
            [],
            [Tone(Pitch.DONG, octave=1)],
        ),
    ),
    (
        Tone(Pitch.DONG, octave=2),
        Position.REYONG_3,
        (
            [Tone(Pitch.DONG, octave=2)],
            [Tone(Pitch.DONG, octave=2)],
            [],
            [],
        ),
    ),
]


@pytest.mark.parametrize("tone, position, expected", tone_range_data)
def test_get_tones_within_range(tone, position, expected):
    load_settings_gk()
    for i, (extended_range, match_octave) in enumerate(product([True, False], [True, False])):
        assert Instrument.get_tones_within_range(tone, position, extended_range, match_octave) == expected[i]


kempyung_tone_data = [
    [
        Tone(Pitch.DONG, 1),
        Position.PEMADE_SANGSIH,
        (
            [Tone(Pitch.DANG, 1)],  # extended_range==True, exact_match==True
            [Tone(Pitch.DANG, 1), Tone(Pitch.DANG, 0)],  # extended_range==True, exact_match==False
            [Tone(Pitch.DANG, 1)],  # extended_range==False, exact_match==True
            [Tone(Pitch.DANG, 1), Tone(Pitch.DANG, 0)],  # extended_range==False, exact_match==False
        ),
    ],
    [
        Tone(Pitch.DUNG, 0),
        Position.PEMADE_SANGSIH,
        (
            [Tone(Pitch.DONG, 1)],
            [Tone(Pitch.DONG, 1), Tone(Pitch.DONG, 0)],
            [Tone(Pitch.DONG, 1)],
            [Tone(Pitch.DONG, 1), Tone(Pitch.DONG, 0)],
        ),
    ],
    [
        Tone(Pitch.DANG, 1),
        Position.PEMADE_SANGSIH,
        (
            [],
            [Tone(Pitch.DENG, 1), Tone(Pitch.DENG, 0)],
            [],
            [Tone(Pitch.DENG, 1), Tone(Pitch.DENG, 0)],
        ),
    ],
    [
        Tone(Pitch.DANG, 1),
        Position.REYONG_2,
        (
            [],
            [Tone(Pitch.DENG, 1)],
            [],
            [Tone(Pitch.DENG, 1)],
        ),
    ],
    [
        Tone(Pitch.DING, 2),
        Position.REYONG_2,
        (
            [],
            [Tone(Pitch.DUNG, 1)],
            [],
            [],
        ),
    ],
    [
        Tone(Pitch.DENG, 0),
        Position.REYONG_2,
        (
            [Tone(Pitch.DING, 1)],
            [Tone(Pitch.DING, 1)],
            [Tone(Pitch.DING, 1)],
            [Tone(Pitch.DING, 1)],
        ),
    ],
]


@pytest.mark.parametrize("tone, position, expected", kempyung_tone_data)
def test_get_kempyung_tones(tone, position, expected):
    for i, (extended_range, within_octave) in enumerate(product([True, False], [True, False])):
        assert Instrument.get_kempyung_tones_within_range(tone, position, extended_range, within_octave) == expected[i]


data_shared_notation_rule = [
    (
        Position.PEMADE_SANGSIH,
        {Position.PEMADE_SANGSIH, Position.KANTILAN_SANGSIH},
        [RuleValue.SAME_TONE],
    ),
    (
        Position.PEMADE_SANGSIH,
        {Position.PEMADE_POLOS, Position.PEMADE_SANGSIH},
        [RuleValue.EXACT_KEMPYUNG, RuleValue.SAME_TONE, RuleValue.SAME_PITCH],
    ),
    (
        Position.PEMADE_SANGSIH,
        {Position.UGAL, Position.PEMADE_SANGSIH},
        [RuleValue.EXACT_KEMPYUNG, RuleValue.SAME_TONE, RuleValue.SAME_PITCH],
    ),
    (
        Position.REYONG_3,
        {Position.REYONG_1, Position.REYONG_2, Position.REYONG_3, Position.REYONG_4},
        [RuleValue.SAME_PITCH, RuleValue.KEMPYUNG],
    ),
    (
        Position.REYONG_3,
        {
            Position.PEMADE_POLOS,
            Position.PEMADE_SANGSIH,
            Position.REYONG_1,
            Position.REYONG_2,
            Position.REYONG_3,
            Position.REYONG_4,
        },
        [RuleValue.SAME_PITCH, RuleValue.KEMPYUNG],
    ),
    (
        Position.REYONG_3,
        {Position.REYONG_1, Position.REYONG_3},
        [RuleValue.SAME_PITCH_EXTENDED_RANGE],
    ),
    (
        Position.UGAL,
        {
            Position.UGAL,
            Position.PEMADE_POLOS,
            Position.PEMADE_SANGSIH,
            Position.KANTILAN_POLOS,
            Position.KANTILAN_SANGSIH,
        },
        [RuleValue.SAME_TONE, RuleValue.SAME_PITCH],
    ),
]


@pytest.mark.parametrize("position, all_positions, expected", data_shared_notation_rule)
def test_shared_notation_rule(position, all_positions, expected):
    assert Instrument.get_shared_notation_rule(position, all_positions) == expected


P_POLOS = Position.PEMADE_POLOS
P_SANGSIH = Position.PEMADE_SANGSIH
K_POLOS = Position.KANTILAN_POLOS
K_SANGSIH = Position.KANTILAN_SANGSIH
GANGSA = {P_POLOS, P_SANGSIH, K_POLOS, K_SANGSIH}
R_1 = Position.REYONG_1
R_2 = Position.REYONG_2
R_3 = Position.REYONG_3
R_4 = Position.REYONG_4
REYONG = {R_1, R_2, R_3, R_4}

data_shared_notation = [
    [Tone(Pitch.DONG, 0), P_SANGSIH, GANGSA, Tone(Pitch.DANG, 0, RuleValue.EXACT_KEMPYUNG)],
    [Tone(Pitch.DENG, 0), P_SANGSIH, GANGSA, Tone(Pitch.DING, 1, RuleValue.EXACT_KEMPYUNG)],
    [Tone(Pitch.DUNG, 0), P_SANGSIH, GANGSA, Tone(Pitch.DONG, 1, RuleValue.EXACT_KEMPYUNG)],
    [Tone(Pitch.DANG, 0), P_SANGSIH, GANGSA, Tone(Pitch.DENG, 1, RuleValue.EXACT_KEMPYUNG)],
    [Tone(Pitch.DING, 1), P_SANGSIH, GANGSA, Tone(Pitch.DUNG, 1, RuleValue.EXACT_KEMPYUNG)],
    [Tone(Pitch.DONG, 1), P_SANGSIH, GANGSA, Tone(Pitch.DANG, 1, RuleValue.EXACT_KEMPYUNG)],
    [Tone(Pitch.DENG, 1), P_SANGSIH, GANGSA, Tone(Pitch.DING, 2, RuleValue.EXACT_KEMPYUNG)],
    [Tone(Pitch.DUNG, 1), P_SANGSIH, GANGSA, Tone(Pitch.DUNG, 1, RuleValue.SAME_TONE)],
    [Tone(Pitch.DANG, 1), P_SANGSIH, GANGSA, Tone(Pitch.DANG, 1, RuleValue.SAME_TONE)],
    [Tone(Pitch.DING, 2), P_SANGSIH, GANGSA, Tone(Pitch.DING, 2, RuleValue.SAME_TONE)],
    [Tone(Pitch.DONG, 0), P_SANGSIH, {K_SANGSIH, P_SANGSIH}, Tone(Pitch.DONG, 0, RuleValue.SAME_TONE)],
    [Tone(Pitch.DENG, 0), P_SANGSIH, {K_SANGSIH, P_SANGSIH}, Tone(Pitch.DENG, 0, RuleValue.SAME_TONE)],
    [Tone(Pitch.DUNG, 0), P_SANGSIH, {K_SANGSIH, P_SANGSIH}, Tone(Pitch.DUNG, 0, RuleValue.SAME_TONE)],
    [Tone(Pitch.DANG, 0), P_SANGSIH, {K_SANGSIH, P_SANGSIH}, Tone(Pitch.DANG, 0, RuleValue.SAME_TONE)],
    [Tone(Pitch.DING, 1), P_SANGSIH, {K_SANGSIH, P_SANGSIH}, Tone(Pitch.DING, 1, RuleValue.SAME_TONE)],
    [Tone(Pitch.DONG, 1), P_SANGSIH, {K_SANGSIH, P_SANGSIH}, Tone(Pitch.DONG, 1, RuleValue.SAME_TONE)],
    [Tone(Pitch.DENG, 1), P_SANGSIH, {K_SANGSIH, P_SANGSIH}, Tone(Pitch.DENG, 1, RuleValue.SAME_TONE)],
    [Tone(Pitch.DUNG, 1), P_SANGSIH, {K_SANGSIH, P_SANGSIH}, Tone(Pitch.DUNG, 1, RuleValue.SAME_TONE)],
    [Tone(Pitch.DANG, 1), P_SANGSIH, {K_SANGSIH, P_SANGSIH}, Tone(Pitch.DANG, 1, RuleValue.SAME_TONE)],
    [Tone(Pitch.DING, 2), P_SANGSIH, {K_SANGSIH, P_SANGSIH}, Tone(Pitch.DING, 2, RuleValue.SAME_TONE)],
    [Tone(Pitch.DENG, 0), R_1, REYONG, Tone(Pitch.DENG, 0, RuleValue.SAME_PITCH)],
    [Tone(Pitch.DUNG, 0), R_1, REYONG, Tone(Pitch.DUNG, 0, RuleValue.SAME_PITCH)],
    [Tone(Pitch.DANG, 0), R_1, REYONG, Tone(Pitch.DANG, 0, RuleValue.SAME_PITCH)],
    [Tone(Pitch.DING, 1), R_1, REYONG, Tone(Pitch.DUNG, 0, RuleValue.KEMPYUNG)],
    [Tone(Pitch.DONG, 1), R_1, REYONG, Tone(Pitch.DANG, 0, RuleValue.KEMPYUNG)],
    [Tone(Pitch.DENG, 0), R_2, REYONG, Tone(Pitch.DENG, 1, RuleValue.SAME_PITCH)],
    [Tone(Pitch.DUNG, 0), R_2, REYONG, Tone(Pitch.DONG, 1, RuleValue.KEMPYUNG)],
    [Tone(Pitch.DANG, 0), R_2, REYONG, Tone(Pitch.DENG, 1, RuleValue.KEMPYUNG)],
    [Tone(Pitch.DING, 1), R_2, REYONG, Tone(Pitch.DING, 1, RuleValue.SAME_PITCH)],
    [Tone(Pitch.DONG, 1), R_2, REYONG, Tone(Pitch.DONG, 1, RuleValue.SAME_PITCH)],
    [Tone(Pitch.DENG, 0), R_3, REYONG, Tone(Pitch.DING, 2, RuleValue.KEMPYUNG)],
    [Tone(Pitch.DUNG, 0), R_3, REYONG, Tone(Pitch.DUNG, 1, RuleValue.SAME_PITCH)],
    [Tone(Pitch.DANG, 0), R_3, REYONG, Tone(Pitch.DANG, 1, RuleValue.SAME_PITCH)],
    [Tone(Pitch.DING, 1), R_3, REYONG, Tone(Pitch.DING, 2, RuleValue.SAME_PITCH)],
    [Tone(Pitch.DONG, 1), R_3, REYONG, Tone(Pitch.DANG, 1, RuleValue.KEMPYUNG)],
    [Tone(Pitch.DENG, 0), R_3, {R_1, R_3}, Tone(Pitch.DENG, 1, RuleValue.SAME_PITCH_EXTENDED_RANGE)],
    [Tone(Pitch.DUNG, 0), R_3, {R_1, R_3}, Tone(Pitch.DUNG, 1, RuleValue.SAME_PITCH_EXTENDED_RANGE)],
    [Tone(Pitch.DANG, 0), R_3, {R_1, R_3}, Tone(Pitch.DANG, 1, RuleValue.SAME_PITCH_EXTENDED_RANGE)],
    [Tone(Pitch.DING, 1), R_3, {R_1, R_3}, Tone(Pitch.DING, 2, RuleValue.SAME_PITCH_EXTENDED_RANGE)],
    [Tone(Pitch.DONG, 1), R_3, {R_1, R_3}, Tone(Pitch.DONG, 2, RuleValue.SAME_PITCH_EXTENDED_RANGE)],
    [Tone(Pitch.DENG, 0), R_4, REYONG, Tone(Pitch.DENG, 2, RuleValue.SAME_PITCH)],
    [Tone(Pitch.DUNG, 0), R_4, REYONG, Tone(Pitch.DUNG, 2, RuleValue.SAME_PITCH)],
    [Tone(Pitch.DANG, 0), R_4, REYONG, Tone(Pitch.DENG, 2, RuleValue.KEMPYUNG)],
    [Tone(Pitch.DING, 1), R_4, REYONG, Tone(Pitch.DUNG, 2, RuleValue.KEMPYUNG)],
    [Tone(Pitch.DONG, 1), R_4, REYONG, Tone(Pitch.DONG, 2, RuleValue.SAME_PITCH)],
    [Tone(Pitch.DENG, 0), R_4, {R_2, R_4}, Tone(Pitch.DENG, 2, RuleValue.SAME_PITCH_EXTENDED_RANGE)],
    [Tone(Pitch.DUNG, 0), R_4, {R_2, R_4}, Tone(Pitch.DUNG, 2, RuleValue.SAME_PITCH_EXTENDED_RANGE)],
    [Tone(Pitch.DANG, 0), R_4, {R_2, R_4}, Tone(Pitch.DANG, 1, RuleValue.SAME_PITCH_EXTENDED_RANGE)],
    [Tone(Pitch.DING, 1), R_4, {R_2, R_4}, Tone(Pitch.DING, 2, RuleValue.SAME_PITCH_EXTENDED_RANGE)],
    [Tone(Pitch.DONG, 1), R_4, {R_2, R_4}, Tone(Pitch.DONG, 2, RuleValue.SAME_PITCH_EXTENDED_RANGE)],
]


@pytest.mark.parametrize("tone, position, all_positions, expected", data_shared_notation)
def test_apply_unisono_rule(tone, position, all_positions, expected):
    tone = Instrument.cast_to_position(tone, position, all_positions)
    assert tone == expected
