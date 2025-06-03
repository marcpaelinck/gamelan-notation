# pylint: disable=missing-module-docstring, missing-class-docstring, missing-function-docstring, line-too-long, invalid-name

from src.common.constants import DEFAULT, Position
from src.common.notes import Note
from src.notation2midi.pipeline.score_to_notation import ScoreToNotationAgent
from src.settings.constants import InstrumentFields
from src.settings.settings import Settings
from tests.conftest import BaseUnitTestCase
from tests.src.utils_for_tests import PositionNote, create_gongan

# pylint: disable=protected-access


class ScoreToNotationTester(BaseUnitTestCase):

    def setUp(self):
        self.settings = Settings.get(notation_id="test-gongkebyar", part_id="full")
        self.symbol_to_note_lookup = {(note.position, note.symbol): note for note in Note.VALIDNOTES}

        self.notation_data = [
            (["i", "I", "o", "O", "e", "E", "u", "U", "a", "A"], "iIoOeEuUaA"),
            (["i", "o", "-", "e", "u", "-", "a", "i<"], "io-eu-ai<"),
            (["i/", "o", "-", "e/", "u", "-", "a/", "i</"], "i/o-e/u-a/i</"),
        ]

        PP = PositionNote(position=Position.PEMADE_POLOS)
        PS = PositionNote(position=Position.PEMADE_SANGSIH)
        # fmt: off
        self.gongan_data = [
            (
                create_gongan(
                    1,
                    {PP.position: {
                        DEFAULT: [[PP.DANG0, PP.DANG0], [PP.DONG1, PP.DONG1], [PP.DING1, PP.DING1], [PP.DENG1, PP.DENG1],
                                 [PP.DONG1, PP.DONG1], [PP.DENG1, PP.DENG1], [PP.DING1, PP.DING1], [PP.DONG1, PP.DONG1]]},
                    PS.position: {
                        DEFAULT: [[PS.DENG1, PS.DENG1], [PS.DANG1, PS.DANG1], [PS.DUNG1, PS.DUNG1], [PS.DING2, PS.DING2],
                                 [PS.DANG1, PS.DANG1], [PS.DING2, PS.DING2], [PS.DUNG1, PS.DUNG1], [PS.DANG1, PS.DANG1]]}
                    },
                ),
                [
                    {InstrumentFields.POSITION: "PEMADE_P", 1: "a,a,", 2: "oo", 3: "ii", 4: "ee", 5: "oo", 6: "ee", 7: "ii", 8: "oo"},
                    {InstrumentFields.POSITION: "PEMADE_S", 1: "ee", 2: "aa", 3: "uu", 4: "i<i<", 5: "aa", 6: "i<i<", 7: "uu", 8: "aa"},
                    {InstrumentFields.POSITION: "", 1: "", 2: "", 3: "", 4: "", 5: "", 6: "", 7: "", 8: ""},
                ],
            )
        ]
        # fmt: on

    def test_notelist_to_string(self):
        agent = ScoreToNotationAgent(self.settings, None)
        for chars, expected in self.notation_data:
            with self.subTest(chars=chars):
                char_list = [self.symbol_to_note_lookup[(Position.PEMADE_POLOS, c)] for c in chars]
                self.assertEqual(agent._notelist_to_string(char_list), expected)

    def test_gongan_to_records(self):
        agent = ScoreToNotationAgent(self.settings, None)
        for gongan, expected in self.gongan_data:
            with self.subTest(gongan=gongan.id):
                self.assertEqual(agent._gongan_to_records(gongan), expected, "Failed for gongan %s" % gongan.id)
