from itertools import product
from typing import Any

from src.common.constants import (
    InstrumentGroup,
    PatternType,
    Pitch,
    Position,
    RuleValue,
    Stroke,
)
from src.common.notes import Note, Tone
from src.notation2midi.rules.rule import Instrument
from src.notation2midi.rules.rule_cast_to_position import RuleCastToPosition
from src.settings.constants import NoteFields
from src.settings.settings import Settings
from tests.conftest import BaseUnitTestCase


class ValidNoteTester(BaseUnitTestCase):

    def load_settings(self, group: InstrumentGroup) -> dict:
        if group is InstrumentGroup.GONG_KEBYAR:
            composition = "test-gongkebyar"
        elif group is InstrumentGroup.SEMAR_PAGULINGAN:
            composition = "test-semarpagulingan"
        else:
            raise ValueError(f"invalid instrument group {group}")
        return Settings.get(notation_id=composition, part_id="full")

    # Combinations that will be tested (contains both valid and invalid combinations)
    TRY_COMBINATIONS: list[dict[str, Any]] = [
        {
            NoteFields.POSITION.value: position,
            NoteFields.PITCH.value: pitch,
            NoteFields.OCTAVE.value: octave,
            NoteFields.EFFECT.value: effect,
            NoteFields.NOTE_VALUE.value: duration,
        }
        for position in (Position.PEMADE_POLOS, Position.JEGOGAN, Position.REYONG_1)
        for pitch in [Pitch.DING, Pitch.DAING, Pitch.STRIKE, Pitch.DAG, Pitch.DENGDING]
        for octave in (1, 2)
        for effect in [Stroke.OPEN, Stroke.MUTED, Stroke.GRACE_NOTE, PatternType.TREMOLO]
        for duration in (0, 0.25, 1.0)
    ]
    # fmt: off
    # pylint: disable=line-too-long
    # Any combination of values from VALID_PITCH_OCTAVE and VALID_STROKE_DURATION for a given position is valid.
    VALID_PITCH_OCTAVE = {
        InstrumentGroup.SEMAR_PAGULINGAN: {
            Position.PEMADE_POLOS: [(Pitch.DING, 1), (Pitch.DONG, 1), (Pitch.DENG, 1), (Pitch.DEUNG, 1), (Pitch.DUNG, 1), (Pitch.DANG, 1), (Pitch.DAING, 1)],
            Position.JEGOGAN: [(Pitch.DING, 1), (Pitch.DONG, 1), (Pitch.DENG, 1), (Pitch.DEUNG, 1), (Pitch.DUNG, 1), (Pitch.DANG, 1), (Pitch.DAING, 1)],
            Position.REYONG_1: [],
        },
        InstrumentGroup.GONG_KEBYAR: {
            Position.PEMADE_POLOS: [ (Pitch.DONG, 0), (Pitch.DENG, 0), (Pitch.DUNG, 0), (Pitch.DANG, 0), (Pitch.DING, 1), (Pitch.DONG, 1),  
                                    (Pitch.DENG, 1), (Pitch.DUNG, 1), (Pitch.DANG, 1), (Pitch.DING, 2)],
            Position.JEGOGAN: [(Pitch.DING, 1), (Pitch.DONG, 1), (Pitch.DENG, 1), (Pitch.DUNG, 1), (Pitch.DANG, 1)],
            Position.REYONG_1: [(Pitch.DENG, 0), (Pitch.DUNG, 0), (Pitch.DANG, 0), (Pitch.DING, 1), (Pitch.DONG, 1), (Pitch.DENGDING, 0), (Pitch.STRIKE, None),
                                (Pitch.BYONG, None)],
        },
    }
    ANY = "any"
    VALID_PITCH_STROKE = {
        InstrumentGroup.SEMAR_PAGULINGAN: {
            Position.PEMADE_POLOS: list(product([Pitch.DING, Pitch.DONG, Pitch.DENG, Pitch.DEUNG,Pitch.DUNG, Pitch.DANG, Pitch.DAING], 
                                                [Stroke.OPEN, Stroke.ABBREVIATED, Stroke.MUTED, Stroke.GRACE_NOTE, PatternType.TREMOLO, PatternType.TREMOLO_ACCELERATING, PatternType.NOROT])),
            Position.JEGOGAN: list(product([Pitch.DING, Pitch.DONG, Pitch.DENG, Pitch.DEUNG,Pitch.DUNG, Pitch.DANG, Pitch.DAING], 
                                                [Stroke.OPEN, Stroke.ABBREVIATED, Stroke.MUTED, PatternType.TREMOLO, PatternType.TREMOLO_ACCELERATING])),
            Position.REYONG_1: [],
        },
        InstrumentGroup.GONG_KEBYAR: {
            Position.PEMADE_POLOS: list(product([Pitch.DING, Pitch.DONG, Pitch.DENG, Pitch.DUNG, Pitch.DANG], 
                                                [Stroke.OPEN, Stroke.ABBREVIATED, Stroke.MUTED, Stroke.GRACE_NOTE, PatternType.TREMOLO, PatternType.TREMOLO_ACCELERATING, PatternType.NOROT])),
            Position.JEGOGAN: list(product([Pitch.DING, Pitch.DONG, Pitch.DENG, Pitch.DUNG, Pitch.DANG], 
                                                [Stroke.OPEN, Stroke.ABBREVIATED, Stroke.MUTED, PatternType.TREMOLO, PatternType.TREMOLO_ACCELERATING])),
            Position.REYONG_1: list(product([Pitch.DENG, Pitch.DUNG, Pitch.DANG, Pitch.DING, Pitch.DONG], 
                                                [Stroke.OPEN, Stroke.ABBREVIATED, Stroke.MUTED, PatternType.TREMOLO, PatternType.TREMOLO_ACCELERATING, PatternType.NOROT])),
        },
    }
    # fmt: on

    @classmethod
    def is_valid_combination(
        cls, group: InstrumentGroup, combination: dict[str, Any], anyduration: bool = False
    ) -> bool:
        """Determines the expected validity of a combination from TRY_COMBINATIONS by comparing its values
           with VALID_PITCH_OCTAVE and VALID_STROKE_DURATION.
        Args:
            group (InstrumentGroup):
            combination (dict[str, Any]): combination of pitch, octave and effect given as a record str->value
        """
        position = combination[NoteFields.POSITION.value]
        valid_pitch_octave = (combination["pitch"], combination["octave"]) in cls.VALID_PITCH_OCTAVE[group][position]
        valid_pitch_effect = (combination["pitch"], combination["effect"]) in cls.VALID_PITCH_STROKE[group][position]
        return valid_pitch_octave and valid_pitch_effect

    def test_returns_only_valid_notes(self):
        """Tests each combination in TRY_COMBINATIONS. Check that only Note objects with valid combinations
        of attributes can be created. Any invalid combination should raise an exception.
        """
        for group in [InstrumentGroup.GONG_KEBYAR, InstrumentGroup.SEMAR_PAGULINGAN]:
            self.load_settings(group)
            for combination in self.TRY_COMBINATIONS:
                with self.subTest(combination=combination):
                    note = Note(**combination)  # returns None for invalid combinations
                    if self.is_valid_combination(group, combination):
                        is_valid = True
                        self.assertIsNotNone(note)
                    elif self.is_valid_combination(group, combination, anyduration=True):
                        is_valid = True
                        self.assertIsNone(note)
                    else:
                        is_valid = False
                    if is_valid:
                        try:
                            self.assertIsNotNone(Note(symbol="", **combination))
                        except ValueError:
                            self.fail("Unexpected failure for a valid combination.")
                    else:
                        self.assertRaises(ValueError, Note, symbol="", **combination)


class ToneTester(BaseUnitTestCase):

    def load_settings_sp(self):
        # Create mock notation and converter for semar pagulingan score
        Settings.get(notation_id="test-semarpagulingan", part_id="full")

    def load_settings_gk(self):
        # Create mock notation and converter for gong kebyar score with beat at end
        Settings.get(notation_id="test-gongkebyar", part_id="full")

    # fmt: off
    tone_range_data = [
        # tone, position, expected result of get_kempyung_tones_within_range(tone, position, extended_range, exact_match)
        # expected = results for ([extended_range, exact_match] for extended_range, exact_match in (True, True), (True, False) (False, True), (False, False))
        (Tone(pitch=Pitch.DONG, octave=1), Position.PEMADE_POLOS, 
            ([Tone(pitch=Pitch.DONG, octave=1)], [Tone(pitch=Pitch.DONG, octave=1), Tone(pitch=Pitch.DONG, octave=0)], [Tone(pitch=Pitch.DONG, octave=1)], [Tone(pitch=Pitch.DONG, octave=1), Tone(pitch=Pitch.DONG, octave=0),])
        ),
        (Tone(pitch=Pitch.DONG, octave=2), Position.REYONG_2, ([], [Tone(pitch=Pitch.DONG, octave=1)], [],[Tone(pitch=Pitch.DONG, octave=1)])),
        (Tone(pitch=Pitch.DONG, octave=2), Position.REYONG_3, ([Tone(pitch=Pitch.DONG, octave=2)], [Tone(pitch=Pitch.DONG, octave=2)], [], []))
    ]
    # fmt: on

    def test_get_tones_within_range(self):
        self.load_settings_gk()
        for tone, position, expected in self.tone_range_data:
            with self.subTest(tone=tone, position=position):
                for i, (extended_range, match_octave) in enumerate(product([True, False], [True, False])):
                    self.assertEqual(
                        Instrument.get_tones_within_range(tone, position, extended_range, match_octave), expected[i]
                    )


class RuleTester(BaseUnitTestCase):

    def setUp(self):
        # Create mock notation and converter for gong kebyar score with beat at end
        Settings.get(notation_id="test-gongkebyar", part_id="full")

    # fmt: off
    kempyung_tone_data = [
        # tone, position, expected result of get_kempyung_tones_within_range(tone, position, extended_range, exact_match)
        # expected = results for ([extended_range, exact_match] for extended_range, exact_match in (True, True), (True, False) (False, True), (False, False))
        [Tone(pitch=Pitch.DONG, octave=1), Position.PEMADE_SANGSIH, ([Tone(pitch=Pitch.DANG, octave=1)], [Tone(pitch=Pitch.DANG, octave=1), Tone(pitch=Pitch.DANG, octave=0)], [Tone(pitch=Pitch.DANG, octave=1)], [Tone(pitch=Pitch.DANG, octave=1), Tone(pitch=Pitch.DANG, octave=0)])],
        [Tone(pitch=Pitch.DUNG, octave=0), Position.PEMADE_SANGSIH, ([Tone(pitch=Pitch.DONG, octave=1)], [Tone(pitch=Pitch.DONG, octave=1), Tone(pitch=Pitch.DONG, octave=0)],[Tone(pitch=Pitch.DONG, octave=1)],[Tone(pitch=Pitch.DONG, octave=1), Tone(pitch=Pitch.DONG, octave=0)])],
        [Tone(pitch=Pitch.DANG, octave=1), Position.PEMADE_SANGSIH, ([], [Tone(pitch=Pitch.DENG, octave=1), Tone(pitch=Pitch.DENG, octave=0)], [], [Tone(pitch=Pitch.DENG, octave=1), Tone(pitch=Pitch.DENG, octave=0)])],
        [Tone(pitch=Pitch.DANG, octave=1), Position.REYONG_2, ([], [Tone(pitch=Pitch.DENG, octave=1)], [], [Tone(pitch=Pitch.DENG, octave=1)])],
        [Tone(pitch=Pitch.DING, octave=2), Position.REYONG_2, ([], [Tone(pitch=Pitch.DUNG, octave=1)], [], [])],
        [Tone(pitch=Pitch.DENG, octave=0), Position.REYONG_2, ([Tone(pitch=Pitch.DING, octave=1)], [Tone(pitch=Pitch.DING, octave=1)],[Tone(pitch=Pitch.DING, octave=1)], [Tone(pitch=Pitch.DING, octave=1)])]
    ]
    # fmt: on

    def test_get_kempyung_tones(self):
        for tone, position, expected in self.kempyung_tone_data:
            for i, (extended_range, exact_match) in enumerate(product([True, False], [True, False])):
                with self.subTest(tone=tone, position=position, extended_range=extended_range, exact_match=exact_match):
                    self.assertEqual(
                        RuleCastToPosition.get_kempyung_tones_within_range(tone, position, extended_range, exact_match),
                        expected[i],
                    )

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

    def test_shared_notation_rule(self):
        for position, all_positions, expected in self.data_shared_notation_rule:
            with self.subTest(position=position, all_positions=all_positions):
                self.assertEqual(RuleCastToPosition.get_shared_notation_rule(position, all_positions), expected)

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
        [
            Tone(pitch=Pitch.DONG, octave=0),
            P_SANGSIH,
            GANGSA,
            Tone(pitch=Pitch.DANG, octave=0, transformation=RuleValue.EXACT_KEMPYUNG),
        ],
        [
            Tone(pitch=Pitch.DENG, octave=0),
            P_SANGSIH,
            GANGSA,
            Tone(pitch=Pitch.DING, octave=1, transformation=RuleValue.EXACT_KEMPYUNG),
        ],
        [
            Tone(pitch=Pitch.DUNG, octave=0),
            P_SANGSIH,
            GANGSA,
            Tone(pitch=Pitch.DONG, octave=1, transformation=RuleValue.EXACT_KEMPYUNG),
        ],
        [
            Tone(pitch=Pitch.DANG, octave=0),
            P_SANGSIH,
            GANGSA,
            Tone(pitch=Pitch.DENG, octave=1, transformation=RuleValue.EXACT_KEMPYUNG),
        ],
        [
            Tone(pitch=Pitch.DING, octave=1),
            P_SANGSIH,
            GANGSA,
            Tone(pitch=Pitch.DUNG, octave=1, transformation=RuleValue.EXACT_KEMPYUNG),
        ],
        [
            Tone(pitch=Pitch.DONG, octave=1),
            P_SANGSIH,
            GANGSA,
            Tone(pitch=Pitch.DANG, octave=1, transformation=RuleValue.EXACT_KEMPYUNG),
        ],
        [
            Tone(pitch=Pitch.DENG, octave=1),
            P_SANGSIH,
            GANGSA,
            Tone(pitch=Pitch.DING, octave=2, transformation=RuleValue.EXACT_KEMPYUNG),
        ],
        [
            Tone(pitch=Pitch.DUNG, octave=1),
            P_SANGSIH,
            GANGSA,
            Tone(pitch=Pitch.DUNG, octave=1, transformation=RuleValue.SAME_TONE),
        ],
        [
            Tone(pitch=Pitch.DANG, octave=1),
            P_SANGSIH,
            GANGSA,
            Tone(pitch=Pitch.DANG, octave=1, transformation=RuleValue.SAME_TONE),
        ],
        [
            Tone(pitch=Pitch.DING, octave=2),
            P_SANGSIH,
            GANGSA,
            Tone(pitch=Pitch.DING, octave=2, transformation=RuleValue.SAME_TONE),
        ],
        [
            Tone(pitch=Pitch.DONG, octave=0),
            P_SANGSIH,
            {K_SANGSIH, P_SANGSIH},
            Tone(pitch=Pitch.DONG, octave=0, transformation=RuleValue.SAME_TONE),
        ],
        [
            Tone(pitch=Pitch.DENG, octave=0),
            P_SANGSIH,
            {K_SANGSIH, P_SANGSIH},
            Tone(pitch=Pitch.DENG, octave=0, transformation=RuleValue.SAME_TONE),
        ],
        [
            Tone(pitch=Pitch.DUNG, octave=0),
            P_SANGSIH,
            {K_SANGSIH, P_SANGSIH},
            Tone(pitch=Pitch.DUNG, octave=0, transformation=RuleValue.SAME_TONE),
        ],
        [
            Tone(pitch=Pitch.DANG, octave=0),
            P_SANGSIH,
            {K_SANGSIH, P_SANGSIH},
            Tone(pitch=Pitch.DANG, octave=0, transformation=RuleValue.SAME_TONE),
        ],
        [
            Tone(pitch=Pitch.DING, octave=1),
            P_SANGSIH,
            {K_SANGSIH, P_SANGSIH},
            Tone(pitch=Pitch.DING, octave=1, transformation=RuleValue.SAME_TONE),
        ],
        [
            Tone(pitch=Pitch.DONG, octave=1),
            P_SANGSIH,
            {K_SANGSIH, P_SANGSIH},
            Tone(pitch=Pitch.DONG, octave=1, transformation=RuleValue.SAME_TONE),
        ],
        [
            Tone(pitch=Pitch.DENG, octave=1),
            P_SANGSIH,
            {K_SANGSIH, P_SANGSIH},
            Tone(pitch=Pitch.DENG, octave=1, transformation=RuleValue.SAME_TONE),
        ],
        [
            Tone(pitch=Pitch.DUNG, octave=1),
            P_SANGSIH,
            {K_SANGSIH, P_SANGSIH},
            Tone(pitch=Pitch.DUNG, octave=1, transformation=RuleValue.SAME_TONE),
        ],
        [
            Tone(pitch=Pitch.DANG, octave=1),
            P_SANGSIH,
            {K_SANGSIH, P_SANGSIH},
            Tone(pitch=Pitch.DANG, octave=1, transformation=RuleValue.SAME_TONE),
        ],
        [
            Tone(pitch=Pitch.DING, octave=2),
            P_SANGSIH,
            {K_SANGSIH, P_SANGSIH},
            Tone(pitch=Pitch.DING, octave=2, transformation=RuleValue.SAME_TONE),
        ],
        [
            Tone(pitch=Pitch.DENG, octave=0),
            R_1,
            REYONG,
            Tone(pitch=Pitch.DENG, octave=0, transformation=RuleValue.SAME_PITCH),
        ],
        [
            Tone(pitch=Pitch.DUNG, octave=0),
            R_1,
            REYONG,
            Tone(pitch=Pitch.DUNG, octave=0, transformation=RuleValue.SAME_PITCH),
        ],
        [
            Tone(pitch=Pitch.DANG, octave=0),
            R_1,
            REYONG,
            Tone(pitch=Pitch.DANG, octave=0, transformation=RuleValue.SAME_PITCH),
        ],
        [
            Tone(pitch=Pitch.DING, octave=1),
            R_1,
            REYONG,
            Tone(pitch=Pitch.DUNG, octave=0, transformation=RuleValue.KEMPYUNG),
        ],
        [
            Tone(pitch=Pitch.DONG, octave=1),
            R_1,
            REYONG,
            Tone(pitch=Pitch.DANG, octave=0, transformation=RuleValue.KEMPYUNG),
        ],
        [
            Tone(pitch=Pitch.DENG, octave=0),
            R_2,
            REYONG,
            Tone(pitch=Pitch.DENG, octave=1, transformation=RuleValue.SAME_PITCH),
        ],
        [
            Tone(pitch=Pitch.DUNG, octave=0),
            R_2,
            REYONG,
            Tone(pitch=Pitch.DONG, octave=1, transformation=RuleValue.KEMPYUNG),
        ],
        [
            Tone(pitch=Pitch.DANG, octave=0),
            R_2,
            REYONG,
            Tone(pitch=Pitch.DENG, octave=1, transformation=RuleValue.KEMPYUNG),
        ],
        [
            Tone(pitch=Pitch.DING, octave=1),
            R_2,
            REYONG,
            Tone(pitch=Pitch.DING, octave=1, transformation=RuleValue.SAME_PITCH),
        ],
        [
            Tone(pitch=Pitch.DONG, octave=1),
            R_2,
            REYONG,
            Tone(pitch=Pitch.DONG, octave=1, transformation=RuleValue.SAME_PITCH),
        ],
        [
            Tone(pitch=Pitch.DENG, octave=0),
            R_3,
            REYONG,
            Tone(pitch=Pitch.DING, octave=2, transformation=RuleValue.KEMPYUNG),
        ],
        [
            Tone(pitch=Pitch.DUNG, octave=0),
            R_3,
            REYONG,
            Tone(pitch=Pitch.DUNG, octave=1, transformation=RuleValue.SAME_PITCH),
        ],
        [
            Tone(pitch=Pitch.DANG, octave=0),
            R_3,
            REYONG,
            Tone(pitch=Pitch.DANG, octave=1, transformation=RuleValue.SAME_PITCH),
        ],
        [
            Tone(pitch=Pitch.DING, octave=1),
            R_3,
            REYONG,
            Tone(pitch=Pitch.DING, octave=2, transformation=RuleValue.SAME_PITCH),
        ],
        [
            Tone(pitch=Pitch.DONG, octave=1),
            R_3,
            REYONG,
            Tone(pitch=Pitch.DANG, octave=1, transformation=RuleValue.KEMPYUNG),
        ],
        [
            Tone(pitch=Pitch.DENG, octave=0),
            R_3,
            {R_1, R_3},
            Tone(pitch=Pitch.DENG, octave=1, transformation=RuleValue.SAME_PITCH_EXTENDED_RANGE),
        ],
        [
            Tone(pitch=Pitch.DUNG, octave=0),
            R_3,
            {R_1, R_3},
            Tone(pitch=Pitch.DUNG, octave=1, transformation=RuleValue.SAME_PITCH_EXTENDED_RANGE),
        ],
        [
            Tone(pitch=Pitch.DANG, octave=0),
            R_3,
            {R_1, R_3},
            Tone(pitch=Pitch.DANG, octave=1, transformation=RuleValue.SAME_PITCH_EXTENDED_RANGE),
        ],
        [
            Tone(pitch=Pitch.DING, octave=1),
            R_3,
            {R_1, R_3},
            Tone(pitch=Pitch.DING, octave=2, transformation=RuleValue.SAME_PITCH_EXTENDED_RANGE),
        ],
        [
            Tone(pitch=Pitch.DONG, octave=1),
            R_3,
            {R_1, R_3},
            Tone(pitch=Pitch.DONG, octave=2, transformation=RuleValue.SAME_PITCH_EXTENDED_RANGE),
        ],
        [
            Tone(pitch=Pitch.DENG, octave=0),
            R_4,
            REYONG,
            Tone(pitch=Pitch.DENG, octave=2, transformation=RuleValue.SAME_PITCH),
        ],
        [
            Tone(pitch=Pitch.DUNG, octave=0),
            R_4,
            REYONG,
            Tone(pitch=Pitch.DUNG, octave=2, transformation=RuleValue.SAME_PITCH),
        ],
        [
            Tone(pitch=Pitch.DANG, octave=0),
            R_4,
            REYONG,
            Tone(pitch=Pitch.DENG, octave=2, transformation=RuleValue.KEMPYUNG),
        ],
        [
            Tone(pitch=Pitch.DING, octave=1),
            R_4,
            REYONG,
            Tone(pitch=Pitch.DUNG, octave=2, transformation=RuleValue.KEMPYUNG),
        ],
        [
            Tone(pitch=Pitch.DONG, octave=1),
            R_4,
            REYONG,
            Tone(pitch=Pitch.DONG, octave=2, transformation=RuleValue.SAME_PITCH),
        ],
        [
            Tone(pitch=Pitch.DENG, octave=0),
            R_4,
            {R_2, R_4},
            Tone(pitch=Pitch.DENG, octave=2, transformation=RuleValue.SAME_PITCH_EXTENDED_RANGE),
        ],
        [
            Tone(pitch=Pitch.DUNG, octave=0),
            R_4,
            {R_2, R_4},
            Tone(pitch=Pitch.DUNG, octave=2, transformation=RuleValue.SAME_PITCH_EXTENDED_RANGE),
        ],
        [
            Tone(pitch=Pitch.DANG, octave=0),
            R_4,
            {R_2, R_4},
            Tone(pitch=Pitch.DANG, octave=1, transformation=RuleValue.SAME_PITCH_EXTENDED_RANGE),
        ],
        [
            Tone(pitch=Pitch.DING, octave=1),
            R_4,
            {R_2, R_4},
            Tone(pitch=Pitch.DING, octave=2, transformation=RuleValue.SAME_PITCH_EXTENDED_RANGE),
        ],
        [
            Tone(pitch=Pitch.DONG, octave=1),
            R_4,
            {R_2, R_4},
            Tone(pitch=Pitch.DONG, octave=2, transformation=RuleValue.SAME_PITCH_EXTENDED_RANGE),
        ],
    ]

    def test_apply_unisono_rule(self):
        for tone, position, all_positions, expected in self.data_shared_notation:
            with self.subTest(tone=tone, position=position, all_positions=all_positions):
                cast_tone = RuleCastToPosition.cast_to_position(
                    tone=tone, position=position, all_positions=all_positions, metadata=[]
                )
                self.assertEqual(cast_tone, expected)
