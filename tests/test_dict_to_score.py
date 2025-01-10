import unittest
from unittest.mock import MagicMock

from constants import Position

from src.common.classes import Notation, Score
from src.notation2midi.dict_to_score import DictToScoreConverter


class TestDictToScoreConverter(unittest.TestCase):

    def setUp(self):
        # Mock the Notation object
        self.mock_notation = MagicMock(spec=Notation)
        self.mock_notation.settings = MagicMock()
        self.mock_notation.notation_dict = {
            # Add mock data for notation_dict
        }
        self.converter = DictToScoreConverter(self.mock_notation)

    def test_create_score(self):
        self.converter._create_score_object_model = MagicMock(return_value=Score())
        score = self.converter.create_score()
        self.assertIsInstance(score, Score)
        self.converter._create_score_object_model.assert_called_once()

    def test_get_all_positions(self):
        notation_dict = {
            1: {1: {Position.UGAL: [], Position.CALUNG: []}},
            2: {1: {Position.JEGOGAN: [], Position.GONGS: []}},
        }
        positions = self.converter._get_all_positions(notation_dict)
        expected_positions = {Position.UGAL, Position.CALUNG, Position.JEGOGAN, Position.GONGS}
        self.assertEqual(positions, expected_positions)

    def test_has_kempli_beat(self):
        gongan = MagicMock()
        gongan.get_metadata.return_value = None
        gongan.gongantype = None
        self.assertTrue(self.converter._has_kempli_beat(gongan))

    def test_move_beat_to_start(self):
        # Add test for _move_beat_to_start method
        pass

    def test_create_rest_stave(self):
        rest_stave = self.converter._create_rest_stave(Position.UGAL, Stroke.SILENCE, 2.5)
        self.assertEqual(len(rest_stave), 3)
        self.assertEqual(rest_stave[0].duration, 1)
        self.assertEqual(rest_stave[1].duration, 1)
        self.assertEqual(rest_stave[2].duration, 0.5)

    def test_apply_metadata(self):
        # Add test for _apply_metadata method
        pass

    def test_add_missing_staves(self):
        # Add test for _add_missing_staves method
        pass

    def test_extend_stave(self):
        # Add test for _extend_stave method
        pass

    def test_complement_shorthand_pokok_staves(self):
        # Add test for _complement_shorthand_pokok_staves method
        pass


if __name__ == "__main__":
    unittest.main()
