import unittest

from src.common.constants import Position
from src.common.metadata_classes import (
    KempliMeta,
    MetaData,
    MetaDataSwitch,
    PartMeta,
    SuppressMeta,
    TempoMeta,
    WaitMeta,
)


class MetadataTester(unittest.TestCase):

    metadata = [
        (
            "str param",
            "{PART name=Pengawit}",
            {"metatype": "PART", "name": "Pengawit"},
        ),
        (
            "str param w spaces",
            "{PART name='Pengawit number 1'}",
            {"metatype": "PART", "name": "Pengawit number 1"},
        ),
        (
            "int param",
            "{TEMPO value=70}",
            {"metatype": "TEMPO", "value": 70},
        ),
        (
            "negative int param",
            "{TEMPO value=-70}",
            {"metatype": "TEMPO", "value": -70},
        ),
        (
            "float param",
            "{WAIT seconds=2.25}",
            {"metatype": "WAIT", "seconds": 2.25},
        ),
        (
            "single unquoted str list param",
            "{VALIDATION ignore=[kempyung]}",
            {"metatype": "VALIDATION", "ignore": ["kempyung"]},
        ),
        (
            "single quoted str list param",
            '{VALIDATION ignore=["kempyung"]}',
            {"metatype": "VALIDATION", "ignore": ["kempyung"]},
        ),
        (
            "multiple unquoted str list param",
            "{VALIDATION ignore=[kempyung, kempli,   other]}",
            {"metatype": "VALIDATION", "ignore": ["kempyung", "kempli", "other"]},
        ),
        (
            "multiple quoted str list param",
            '{VALIDATION ignore=["kempyung", "kempli",  "other"]}',
            {"metatype": "VALIDATION", "ignore": ["kempyung", "kempli", "other"]},
        ),
        (
            "multiple mixed str list param",
            '{VALIDATION ignore=[kempyung, kempli,  "other quoted"]}',
            {"metatype": "VALIDATION", "ignore": ["kempyung", "kempli", "other quoted"]},
        ),
        (
            "multiple int list param",
            "{GOTO passes=[4, 5,-6,    7]}",
            {"metatype": "GOTO", "passes": [4, 5, -6, 7]},
        ),
        (
            "multiple mixed param",
            "{LABEL name=TROMPONG_PENYALIT}",
            {"metatype": "LABEL", "name": "TROMPONG_PENYALIT"},
        ),
    ]

    def test_metatdata_validator(self):
        for testname, data, expected in self.metadata:
            with self.subTest(testname=testname, data=data):
                self.assertEqual(MetaData.convert_to_proper_json(data), expected)

    metadata_valid = [
        (
            "PART",
            "{PART name=Pengawit}",
            MetaData(data=PartMeta(metatype="PART", name="Pengawit")),
        ),
        (
            "TEMPO",
            "{TEMPO value=70, passes=[1,3,5]}",
            MetaData(data=TempoMeta(metatype="TEMPO", value=70, passes=[1, 3, 5])),
        ),
        (
            "WAIT",
            "{WAIT seconds=2.75, after=false}",
            MetaData(data=WaitMeta(metatype="WAIT", seconds=2.75, after=False)),
        ),
        (
            "KEMPLI",
            '{KEMPLI beats=[5,6], status="on"}',
            MetaData(data=KempliMeta(metatype="KEMPLI", beats=[5, 6], status=MetaDataSwitch.ON)),
        ),
        (
            "SUPPRESS",
            "{SUPPRESS positions=[gangsa, reyong1], passes=[1], beats=[1,2]}",
            MetaData(
                data=SuppressMeta(
                    metatype="SUPPRESS",
                    positions=[
                        Position.PEMADE_POLOS,
                        Position.PEMADE_SANGSIH,
                        Position.KANTILAN_POLOS,
                        Position.KANTILAN_SANGSIH,
                        Position.REYONG_1,
                    ],
                    passes=[1],
                    beats=[1, 2],
                )
            ),
        ),
    ]

    def test_metatdata_parser(self):
        for testname, data, expected in self.metadata_valid:
            with self.subTest(testname=testname, data=data):
                self.assertEqual(MetaData(data=data), expected)

    metadata_invalid = [
        ("Malformed name", "{@PART name=Pengawit}", "^Err1"),
        ("Invalid name", "{INVALIDNAME name=Pengawit}", "^Err2"),
        ("missing comma", "{KEMPLI beats=[5,6]  status=on}", "^Err3"),
        ("missing equals1", "{KEMPLI beats=[5,6], status on}", "^Err3"),
        ("missing equals2", "{KEMPLI beats: [5,6], status: on}", "^Err3"),
        ("invalid param", "{KEMPLI beats=[5,6], statoos=on}", "^Err4"),
        ("not json", "{KEMPLI beats=[(5,6], status=on}", "^Err5"),
        ("invalid value", "{KEMPLI beats=[5,6], status=wrong}", "validation error"),
    ]

    # Test that invalid values cause an exception with a specific error message
    def test_metatdata_parser_invalids(self):
        for testname, data, errmsg in self.metadata_invalid:
            with self.subTest(testname=testname, data=data):
                self.assertRaisesRegex(Exception, errmsg, MetaData, data=data)
