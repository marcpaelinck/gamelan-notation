import unittest

from src.common.classes import Gongan
from src.notation2midi.score2notation.utils import has_kempli_beat
from tests.conftest import BaseUnitTestCase


class TestUtils(BaseUnitTestCase):

    def setUp(self):
        pass

    def test_measure_to_str(self):
        pass

    def test_clean_staves(self):
        pass

    def test_stringWidth_fromNotes(self):
        pass

    def test_to_aggregated_tags(self):
        pass

    def test_has_kempli_beat(self):
        gongans = [
            ({"id": 1, "metadata": [{"data": {"metatype": "KEMPLI", "status": "on"}}]}, True),
            ({"id": 2, "metadata": [{"data": {"metatype": "KEMPLI", "status": "off"}}]}, False),
            ({"id": 3, "metadata": [{"data": {"metatype": "GONGAN", "type": "regular"}}]}, True),
            ({"id": 4, "metadata": [{"data": {"metatype": "GONGAN", "type": "kebyar"}}]}, False),
            ({"id": 5, "metadata": [{"data": {"metatype": "GONGAN", "type": "gineman"}}]}, False),
        ]
        for record, expected in gongans:
            with self.subTest(msg="subtest failed", record=record):
                gongan = Gongan.model_validate(record)
                self.assertTrue(has_kempli_beat(gongan) == expected, "Failed for gongan %s" % record["id"])

    def test_is_silent(self):
        pass

    def test_aggregate_positions(self):
        pass


if __name__ == "__main__":
    unittest.main()
