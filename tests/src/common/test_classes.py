import unittest
from itertools import product
from typing import Any
from unittest.mock import patch

from src.common.classes import Instrument, Note, Tone
from src.common.constants import (
    InstrumentGroup,
    InstrumentType,
    NoteRecord,
    Pitch,
    Position,
    RuleValue,
    Stroke,
)
from src.settings.constants import NoteFields, Yaml
from src.settings.settings import load_run_settings


class ValidNoteTester(unittest.TestCase):

    @patch("src.settings.settings.SETTINGSFOLDER", "./tests/settings")
    def load_settings_sp(self) -> list[NoteRecord]:
        # Creates a list of valid notes for Semar Pagulingan
        return load_run_settings({Yaml.COMPOSITION: "test-semarpagulingan", Yaml.PART_ID: "full"})

    @patch("src.settings.settings.SETTINGSFOLDER", "./tests/settings")
    def load_settings_gk(self) -> list[NoteRecord]:
        # Creates a list of valid notes for  Gong Kebyar
        return load_run_settings({Yaml.COMPOSITION: "test-gongkebyar", Yaml.PART_ID: "full"})

    # Combinations that will be tested
    def setUp(self):
        self.TRY_COMBINATIONS = [
            {
                NoteFields.POSITION.value: position,
                NoteFields.PITCH.value: pitch,
                NoteFields.OCTAVE.value: octave,
                NoteFields.STROKE.value: stroke,
                NoteFields.DURATION.value: duration,
                NoteFields.REST_AFTER.value: rest_after,
            }
            for position in (Position.PEMADE_POLOS, Position.JEGOGAN, Position.REYONG_1)
            for pitch in [Pitch.DING, Pitch.DAING, Pitch.STRIKE, Pitch.DAG, Pitch.DENGDING]
            for octave in (1, 2)
            for stroke in [Stroke.OPEN, Stroke.MUTED, Stroke.TREMOLO, Stroke.GRACE_NOTE]
            for duration in (0, 0.25, 1.0)
            for rest_after in (0,)
        ]
        # fmt: off
        self.VALID_PITCH_OCTAVE = {
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
        self.VALID_STROKE_DURATION = {
            InstrumentGroup.SEMAR_PAGULINGAN: {
                Position.PEMADE_POLOS: [(Stroke.OPEN, 0.25), (Stroke.OPEN, 0.5), (Stroke.OPEN, 1.0), (Stroke.ABBREVIATED, 0.25), (Stroke.ABBREVIATED, 0.5), 
                                        (Stroke.ABBREVIATED, 1.0), (Stroke.MUTED, 0.25), (Stroke.MUTED, 0.5), (Stroke.MUTED, 1.0), (Stroke.TREMOLO, 1.0), 
                                        (Stroke.TREMOLO_ACCELERATING, 1.0), (Stroke.NOROT, 1.0), (Stroke.GRACE_NOTE, 0.0)],
                Position.JEGOGAN: [(Stroke.OPEN, 0.25), (Stroke.OPEN, 0.5), (Stroke.OPEN, 1.0), (Stroke.ABBREVIATED, 0.25), (Stroke.ABBREVIATED, 0.5), 
                                   (Stroke.ABBREVIATED, 1.0), (Stroke.MUTED, 0.25), (Stroke.MUTED, 0.5), (Stroke.MUTED, 1.0), (Stroke.TREMOLO, 1.0), 
                                   (Stroke.TREMOLO_ACCELERATING, 1.0)],
                Position.REYONG_1: [],
            },
            InstrumentGroup.GONG_KEBYAR: {
                Position.PEMADE_POLOS: [(Stroke.OPEN, 0.25), (Stroke.OPEN, 0.5), (Stroke.OPEN, 1.0), (Stroke.ABBREVIATED, 0.25), (Stroke.ABBREVIATED, 0.5), 
                                        (Stroke.ABBREVIATED, 1.0), (Stroke.MUTED, 0.25), (Stroke.MUTED, 0.5), (Stroke.MUTED, 1.0), (Stroke.TREMOLO, 1.0), 
                                        (Stroke.TREMOLO_ACCELERATING, 1.0), (Stroke.NOROT, 1.0), (Stroke.GRACE_NOTE, 0.0)],
                Position.JEGOGAN: [(Stroke.OPEN, 0.25), (Stroke.OPEN, 0.5), (Stroke.OPEN, 1.0), (Stroke.ABBREVIATED, 0.25), (Stroke.ABBREVIATED, 0.5), 
                                   (Stroke.ABBREVIATED, 1.0), (Stroke.MUTED, 0.25), (Stroke.MUTED, 0.5), (Stroke.MUTED, 1.0), (Stroke.TREMOLO, 1.0), 
                                   (Stroke.TREMOLO_ACCELERATING, 1.0)],
                Position.REYONG_1: [(Stroke.OPEN, 0.25), (Stroke.OPEN, 0.5), (Stroke.OPEN, 1.0), (Stroke.ABBREVIATED, 0.25), (Stroke.ABBREVIATED, 0.5), 
                                    (Stroke.ABBREVIATED, 1.0), (Stroke.MUTED, 0.25), (Stroke.MUTED, 0.5), (Stroke.MUTED, 1.0), (Stroke.TREMOLO, 1.0), 
                                    (Stroke.TREMOLO_ACCELERATING, 1.0), (Stroke.GRACE_NOTE, 0.0)],
            },
        }

    def test_returns_only_valid_notes(self):
        self.load_settings_gk()
        note = Note.get_note(Position.JEGOGAN, Pitch.DING, 1, Stroke.OPEN, 1, 0)
        self.assertIsNotNone(note)
        self.assertRaises(
            ValueError,
            Note,
            instrumenttype=InstrumentType.JEGOGAN,
            position=Position.JEGOGAN,
            symbol="x",
            pitch=Pitch.STRIKE,
            octave=None,
            stroke=Stroke.OPEN,
            duration=1,
            rest_after=0,
        )


class ToneTester(unittest.TestCase):

    @patch("src.settings.settings.SETTINGSFOLDER", "./tests/settings")
    def load_settings_sp(self):
        # Create mock notation and converter for semar pagulingan score
        load_run_settings(notation={Yaml.COMPOSITION: "test-semarpagulingan", Yaml.PART_ID: "full"})

    @patch("src.settings.settings.SETTINGSFOLDER", "./tests/settings")
    def load_settings_gk(self):
        # Create mock notation and converter for gong kebyar score with beat at end
        load_run_settings(notation={Yaml.COMPOSITION: "test-gongkebyar", Yaml.PART_ID: "full"})

    # fmt: off
    tone_range_data = [
        # tone, position, expected result of get_kempyung_tones_within_range(tone, position, extended_range, exact_match)
        # expected = results for ([extended_range, exact_match] for extended_range, exact_match in (True, True), (True, False) (False, True), (False, False))
        (Tone(Pitch.DONG, octave=1), Position.PEMADE_POLOS, 
            ([Tone(Pitch.DONG, octave=1)], [Tone(Pitch.DONG, octave=1), Tone(Pitch.DONG, octave=0)], [Tone(Pitch.DONG, octave=1)], [Tone(Pitch.DONG, octave=1), Tone(Pitch.DONG, octave=0),])
        ),
        (Tone(Pitch.DONG, octave=2), Position.REYONG_2, ([], [Tone(Pitch.DONG, octave=1)], [],[Tone(Pitch.DONG, octave=1)])),
        (Tone(Pitch.DONG, octave=2), Position.REYONG_3, ([Tone(Pitch.DONG, octave=2)], [Tone(Pitch.DONG, octave=2)], [], []))
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


class RuleTester(unittest.TestCase):
    @patch("src.settings.settings.SETTINGSFOLDER", "./tests/settings")
    def setUp(self):
        # Create mock notation and converter for gong kebyar score with beat at end
        load_run_settings(notation={Yaml.COMPOSITION: "test-gongkebyar", Yaml.PART_ID: "full"})

    # fmt: off
    kempyung_tone_data = [
        # tone, position, expected result of get_kempyung_tones_within_range(tone, position, extended_range, exact_match)
        # expected = results for ([extended_range, exact_match] for extended_range, exact_match in (True, True), (True, False) (False, True), (False, False))
        [Tone(Pitch.DONG, 1), Position.PEMADE_SANGSIH, ([Tone(Pitch.DANG, 1)], [Tone(Pitch.DANG, 1), Tone(Pitch.DANG, 0)], [Tone(Pitch.DANG, 1)], [Tone(Pitch.DANG, 1), Tone(Pitch.DANG, 0)])],
        [Tone(Pitch.DUNG, 0), Position.PEMADE_SANGSIH, ([Tone(Pitch.DONG, 1)], [Tone(Pitch.DONG, 1), Tone(Pitch.DONG, 0)],[Tone(Pitch.DONG, 1)],[Tone(Pitch.DONG, 1), Tone(Pitch.DONG, 0)])],
        [Tone(Pitch.DANG, 1), Position.PEMADE_SANGSIH, ([], [Tone(Pitch.DENG, 1), Tone(Pitch.DENG, 0)], [], [Tone(Pitch.DENG, 1), Tone(Pitch.DENG, 0)])],
        [Tone(Pitch.DANG, 1), Position.REYONG_2, ([], [Tone(Pitch.DENG, 1)], [], [Tone(Pitch.DENG, 1)])],
        [Tone(Pitch.DING, 2), Position.REYONG_2, ([], [Tone(Pitch.DUNG, 1)], [], [])],
        [Tone(Pitch.DENG, 0), Position.REYONG_2, ([Tone(Pitch.DING, 1)], [Tone(Pitch.DING, 1)],[Tone(Pitch.DING, 1)], [Tone(Pitch.DING, 1)])]
    ]
    # fmt: on

    def test_get_kempyung_tones(self):
        for tone, position, expected in self.kempyung_tone_data:
            for i, (extended_range, exact_match) in enumerate(product([True, False], [True, False])):
                with self.subTest(tone=tone, position=position, extended_range=extended_range, exact_match=exact_match):
                    self.assertEqual(
                        Instrument.get_kempyung_tones_within_range(tone, position, extended_range, exact_match),
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
                self.assertEqual(Instrument.get_shared_notation_rule(position, all_positions), expected)

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

    def test_apply_unisono_rule(self):
        for tone, position, all_positions, expected in self.data_shared_notation:
            with self.subTest(tone=tone, position=position, all_positions=all_positions):
                cast_tone = Instrument.cast_to_position(tone, position, all_positions)
                self.assertEqual(cast_tone, expected)
