import unittest
from unittest.mock import patch

from src.common.classes import Beat, Gongan, Measure, Note
from src.common.constants import DEFAULT, Position
from src.notation2midi.score2notation.score_to_notation import (
    gongan_to_records,
    notelist_to_string,
)
from src.settings.constants import InstrumentFields, Yaml
from src.settings.settings import load_run_settings


class ScoreToNotationTester(unittest.TestCase):

    def setUp(self):
        load_run_settings({Yaml.COMPOSITION: "test-gongkebyar", Yaml.PART_ID: "full"})
        self.symbol_to_note_lookup = {(note.position, note.symbol): note for note in Note.VALIDNOTES}

        self.notation_data = [
            (["i", "I", "o", "O", "e", "E", "u", "U", "a", "A"], "iIoOeEuUaA"),
            (["i", "o", "-", "e", "u", "-", "a", "i<"], "io-eu-ai<"),
            (["i/", "o", "-", "e/", "u", "-", "a/", "i</"], "i/o-e/u-a/i</"),
        ]

        self.gongan_data = [
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
                                    all_positions=instr,
                                    passes={
                                        DEFAULT: Measure.Pass(
                                            seq=DEFAULT,
                                            notes=[self.symbol_to_note_lookup[(instr, c)] for c in notelist[idx]],
                                        )
                                    },
                                )
                                for instr, notelist in {
                                    # fmt: off
                                    Position.PEMADE_POLOS: [["a,", "a,"], ["o", "o"], ["i", "i"], ["e", "e"], ["o", "o"], ["e", "e"], ["i", "i"], ["o", "o"]],
                                    Position.PEMADE_SANGSIH: [["e", "e"], ["a", "a"], ["u", "u"], ["i<", "i<"], ["a", "a"], ["i<", "i<"], ["u", "u"], ["a", "a"]],
                                }.items()
                                # fmt: on
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

    def test_notelist_to_string(self):
        for chars, expected in self.notation_data:
            with self.subTest(chars=chars):
                char_list = [self.symbol_to_note_lookup[(Position.PEMADE_POLOS, c)] for c in chars]
                self.assertEqual(notelist_to_string(char_list), expected)

    def test_gongan_to_records(self):
        for gongan, expected in self.gongan_data:
            with self.subTest(gongan=gongan):
                self.assertEqual(gongan_to_records(gongan), expected)
