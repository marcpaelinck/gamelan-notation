"""
Tests for the Tatsu based notation parser
"""

from src.common.classes import Position
from src.common.constants import DynamicLevel, ParserTag
from src.notation2midi.classes import MetaDataRecord
from src.notation2midi.metadata_classes import (
    GonganType,
    MetaDataSwitch,
    Scope,
    ValidationProperty,
)
from src.notation2midi.pipeline.parse_notation import NotationParserAgent
from src.settings.settings import Settings
from tests.conftest import BaseUnitTestCase

grammar_header = """
@@grammar::METADATA

start  = "{"  @:metadata "}"  $  ;
"""

# pylint: disable=protected-access


class NotationParserTester(BaseUnitTestCase):
    def setUp(self):
        self.run_settings = Settings.get(notation_id="test-gongkebyar", part_id="full")
        self.parser = NotationParserAgent(self.run_settings)

    metadata = [
        [
            "{DYNAMICS value=f}",
            MetaDataRecord(
                metatype="DYNAMICS",
                line=1,
                abbreviation=DynamicLevel.FORTE,
            ),
        ],
        [
            "{DYNAMICS value=f, first_beat=13, positions=[gangsa]}",
            MetaDataRecord(
                metatype="DYNAMICS",
                line=1,
                abbreviation=DynamicLevel.FORTE,
                first_beat=13,
                positions=[
                    Position.PEMADE_POLOS,
                    Position.PEMADE_SANGSIH,
                    Position.KANTILAN_POLOS,
                    Position.KANTILAN_SANGSIH,
                ],
            ),
        ],
        [
            "{DYNAMICS value=f, positions=[gangsa, reyong], passes=[4, 8, 12]}",
            MetaDataRecord(
                metatype="DYNAMICS",
                line=1,
                abbreviation=DynamicLevel.FORTE,
                passes=[4, 8, 12],
                positions=[
                    Position.PEMADE_POLOS,
                    Position.PEMADE_SANGSIH,
                    Position.KANTILAN_POLOS,
                    Position.KANTILAN_SANGSIH,
                    Position.REYONG_1,
                    Position.REYONG_2,
                    Position.REYONG_3,
                    Position.REYONG_4,
                ],
            ),
        ],
        [
            "{DYNAMICS value=ff,  beat_count=8, pass=[3], positions=[gangsa]}",
            MetaDataRecord(
                metatype="DYNAMICS",
                line=1,
                abbreviation=DynamicLevel.FORTISSIMO,
                beat_count=8,
                passes=[3],
                positions=[
                    Position.PEMADE_POLOS,
                    Position.PEMADE_SANGSIH,
                    Position.KANTILAN_POLOS,
                    Position.KANTILAN_SANGSIH,
                ],
            ),
        ],
        [
            "{DYNAMICS ff  beat_count=8, pass=3, position=gangsa}",
            MetaDataRecord(
                metatype="DYNAMICS",
                line=1,
                abbreviation=DynamicLevel.FORTISSIMO,
                beat_count=8,
                passes=[3],
                positions=[
                    Position.PEMADE_POLOS,
                    Position.PEMADE_SANGSIH,
                    Position.KANTILAN_POLOS,
                    Position.KANTILAN_SANGSIH,
                ],
            ),
        ],
        [
            "{DYNAMICS value=ff first_beat=1 beat_count=8 pass=[3] positions=[gangsa]}",
            MetaDataRecord(
                metatype="DYNAMICS",
                line=1,
                abbreviation=DynamicLevel.FORTISSIMO,
                first_beat=1,
                beat_count=8,
                passes=[3],
                positions=[
                    Position.PEMADE_POLOS,
                    Position.PEMADE_SANGSIH,
                    Position.KANTILAN_POLOS,
                    Position.KANTILAN_SANGSIH,
                ],
            ),
        ],
        ["{GONGAN type=gineman}", MetaDataRecord(metatype="GONGAN", line=1, type=GonganType.GINEMAN)],
        ["{GONGAN kebyar}", MetaDataRecord(metatype="GONGAN", line=1, type=GonganType.KEBYAR)],
        [
            "{GOTO label=D, passes=[3]}",
            MetaDataRecord(metatype="GOTO", line=1, label="D", passes=[3]),
        ],
        [
            "{GOTO label=KAWITAN_ANGSEL, passes=[2,4]}",
            MetaDataRecord(metatype="GOTO", line=1, label="KAWITAN_ANGSEL", passes=[2, 4]),
        ],
        [
            "{GOTO label=END_PENGAWAK, passes=3}",
            MetaDataRecord(metatype="GOTO", line=1, label="END_PENGAWAK", passes=[3]),
        ],
        [
            "{GOTO PENGAWAK_ANGSEL2, passes=[6, 12]}",
            MetaDataRecord(metatype="GOTO", line=1, label="PENGAWAK_ANGSEL2", passes=[6, 12]),
        ],
        [
            "{KEMPLI status=off, beats=[14,15,16]}",
            MetaDataRecord(metatype="KEMPLI", line=1, status=MetaDataSwitch.OFF, beats=[14, 15, 16]),
        ],
        [
            "{KEMPLI status=on, beat=1}",
            MetaDataRecord(metatype="KEMPLI", line=1, status=MetaDataSwitch.ON, beats=[1]),
        ],
        [
            "{KEMPLI off beats=14}",
            MetaDataRecord(metatype="KEMPLI", line=1, status=MetaDataSwitch.OFF, beats=[14]),
        ],
        ["{LABEL name=D}", MetaDataRecord(metatype="LABEL", line=1, name="D")],
        ["{LABEL END_PENGAWAK}", MetaDataRecord(metatype="LABEL", line=1, name="END_PENGAWAK")],
        ["{PART name=batel}", MetaDataRecord(metatype="PART", line=1, name="batel")],
        [
            '{PART name="Pengecet part 2"}',
            MetaDataRecord(metatype="PART", line=1, name="Pengecet part 2"),
        ],
        ["{PART batel}", MetaDataRecord(metatype="PART", line=1, name="batel")],
        ["{REPEAT count=5}", MetaDataRecord(metatype="REPEAT", line=1, count=5)],
        ["{REPEAT 3}", MetaDataRecord(metatype="REPEAT", line=1, count=3)],
        [
            "{SEQUENCE value=[K_REGULAR, K_ANGSEL1, K_ANGSEL1, K_ANGSEL2, K_REGULAR, K_ANGSEL2, K_REGULAR, K_ANGSEL3, K_REGULAR, K_REGULAR, K_FINAL]}",
            MetaDataRecord(
                metatype="SEQUENCE",
                line=1,
                value=[
                    "K_REGULAR",
                    "K_ANGSEL1",
                    "K_ANGSEL1",
                    "K_ANGSEL2",
                    "K_REGULAR",
                    "K_ANGSEL2",
                    "K_REGULAR",
                    "K_ANGSEL3",
                    "K_REGULAR",
                    "K_REGULAR",
                    "K_FINAL",
                ],
            ),
        ],
        [
            "{SEQUENCE [PENG1,PENG2, PENG1, PENG2, PENG3, PENG4, PENG3, PENG4, PENG1, PENG2, FINAL]}",
            MetaDataRecord(
                metatype="SEQUENCE",
                line=1,
                value=[
                    "PENG1",
                    "PENG2",
                    "PENG1",
                    "PENG2",
                    "PENG3",
                    "PENG4",
                    "PENG3",
                    "PENG4",
                    "PENG1",
                    "PENG2",
                    "FINAL",
                ],
            ),
        ],
        [
            '{SUPPRESS positions=["gangsa p", "gangsa s"], beats=[2,3,4,5,6,7,8], passes=[1, 2,3]}',
            MetaDataRecord(
                metatype="SUPPRESS",
                line=1,
                positions=[
                    Position.PEMADE_POLOS,
                    Position.KANTILAN_POLOS,
                    Position.PEMADE_SANGSIH,
                    Position.KANTILAN_SANGSIH,
                ],
                passes=[1, 2, 3],
                beats=[2, 3, 4, 5, 6, 7, 8],
            ),
        ],
        [
            "{SUPPRESS [reyong, gangsa] beat=[1, 2], pass=1}",
            MetaDataRecord(
                metatype="SUPPRESS",
                line=1,
                positions=[
                    Position.REYONG_1,
                    Position.REYONG_2,
                    Position.REYONG_3,
                    Position.REYONG_4,
                    Position.PEMADE_POLOS,
                    Position.PEMADE_SANGSIH,
                    Position.KANTILAN_POLOS,
                    Position.KANTILAN_SANGSIH,
                ],
                passes=[1],
                beats=[1, 2],
            ),
        ],
        [
            "{TEMPO value=100, beat_count=8, pass=[2]}",
            MetaDataRecord(metatype="TEMPO", line=1, value=100, beat_count=8, passes=[2]),
        ],
        [
            "{TEMPO value=100,  beat_count=0}",
            MetaDataRecord(metatype="TEMPO", line=1, value=100, beat_count=0),
        ],
        [
            "{TEMPO 100  beat_count=8, passes=3}",
            MetaDataRecord(metatype="TEMPO", line=1, value=100, beat_count=8, passes=[3]),
        ],
        [
            "{TEMPO value=47, passes=[1,2], first_beat=5, beat_count=3}",
            MetaDataRecord(metatype="TEMPO", line=1, value=47, first_beat=5, beat_count=3, passes=[1, 2]),
        ],
        [
            "{VALIDATION ignore=[kempyung], scope=SCORE}",
            MetaDataRecord(metatype="VALIDATION", scope=Scope.SCORE, line=1, ignore=[ValidationProperty.KEMPYUNG]),
        ],
        [
            '{VALIDATION ["beat-duration"]}',
            MetaDataRecord(metatype="VALIDATION", line=1, ignore=[ValidationProperty.BEAT_DURATION]),
        ],
        ["{WAIT seconds=3}", MetaDataRecord(metatype="WAIT", line=1, seconds=3.0)],
        ["{WAIT 2.25}", MetaDataRecord(metatype="WAIT", line=1, seconds=2.25)],
    ]

    def test_parse_metadata(self):
        for metanotation, expected in self.metadata:
            with self.subTest(notation=metanotation):
                gongan = "ugal\t\n"  # need to append dummy gongan to create valid notation
                notation = self.parser._main(notation="metadata\t" + metanotation + "\n\n" + gongan)
                self.assertEqual(notation.notation_dict[-1][ParserTag.METADATA][0], expected)

    # Tests for range_str_to_list

    correct_ranges = [
        ("1", [1]),
        ("1-3", [1, 2, 3]),
        ("3-4", [3, 4]),
        ("3,4", [3, 4]),
    ]

    bad_ranges = ["1,2,", "realbad", "1-", "-1", "-", ",", "1-4-"]

    # Tests the conversion of optional range indicators following the position name in the score
    def test_range_str_to_list(self):
        for rangestr, expected in self.correct_ranges:
            with self.subTest(rangestr=rangestr):
                self.assertEqual(self.parser._passes_str_to_list(rangestr), expected)

    # Test that invalid values cause a ValueError to be raised
    def test_range_str_to_list_exception(self):
        for rangestr in self.bad_ranges:
            with self.subTest(rangestr=rangestr):
                self.assertRaises(ValueError, self.parser._passes_str_to_list, rangestr)
