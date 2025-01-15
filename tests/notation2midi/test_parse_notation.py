"""
Tests for the Tatsu based notation parser
"""

import pytest

from src.common.classes import Position
from src.common.constants import DynamicLevel
from src.common.metadata_classes import (
    DynamicsMeta,
    GonganMeta,
    GonganType,
    GoToMeta,
    KempliMeta,
    LabelMeta,
    MetaDataSwitch,
    PartMeta,
    RepeatMeta,
    Scope,
    SequenceMeta,
    SuppressMeta,
    TempoMeta,
    ValidationMeta,
    ValidationProperty,
    WaitMeta,
)
from src.notation2midi.notation_parser_tatsu import (
    _create_notation_grammar_model,
    _parse_notation,
)
from src.settings.settings import get_run_settings

grammar_header = """
@@grammar::METADATA

start  = "{"  @:metadata "}"  $  ;
"""


@pytest.fixture
def notation_grammar_model():
    settings = get_run_settings()
    # path = os.path.join(settings.grammars.folder, settings.grammars.notation_filepath)
    # with open(path, "r") as grammarfile:
    #     grammar = grammarfile.read()
    # grammar = grammar_header + grammar
    # model = compile(grammar)
    return _create_notation_grammar_model(settings)


# [notation, expected_parsed_value]
metadata = [
    [
        "{DYNAMICS value=f}",
        DynamicsMeta(
            metatype="DYNAMICS",
            scope=Scope.GONGAN,
            value=DynamicLevel.FORTE,
            first_beat=1,
            beat_count=0,
            passes=[-1],
            positions=[],
        ),
    ],
    [
        "{DYNAMICS value=f, first_beat=13, positions=[gangsa]}",
        DynamicsMeta(
            metatype="DYNAMICS",
            scope=Scope.GONGAN,
            value=DynamicLevel.FORTE,
            first_beat=13,
            beat_count=0,
            passes=[-1],
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
        DynamicsMeta(
            metatype="DYNAMICS",
            scope=Scope.GONGAN,
            value=DynamicLevel.FORTE,
            first_beat=1,
            beat_count=0,
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
        "{DYNAMICS value=ff, first_beat=1, beat_count=8, pass=[3], positions=[gangsa]}",
        DynamicsMeta(
            metatype="DYNAMICS",
            scope=Scope.GONGAN,
            value=DynamicLevel.FORTISSIMO,
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
    [
        "{DYNAMICS ff first_beat=1, beat_count=8, pass=3, position=gangsa}",
        DynamicsMeta(
            metatype="DYNAMICS",
            scope=Scope.GONGAN,
            value=DynamicLevel.FORTISSIMO,
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
    [
        "{DYNAMICS value=ff first_beat=1 beat_count=8 pass=[3] positions=[gangsa]}",
        DynamicsMeta(
            metatype="DYNAMICS",
            scope=Scope.GONGAN,
            value=DynamicLevel.FORTISSIMO,
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
    ["{GONGAN type=gineman}", GonganMeta(metatype="GONGAN", scope=Scope.GONGAN, type=GonganType.GINEMAN)],
    ["{GONGAN kebyar}", GonganMeta(metatype="GONGAN", scope=Scope.GONGAN, type=GonganType.KEBYAR)],
    [
        "{GOTO label=D, passes=[3]}",
        GoToMeta(metatype="GOTO", scope=Scope.GONGAN, label="D", from_beat=None, passes=[3]),
    ],
    [
        "{GOTO label=KAWITAN_ANGSEL, passes=[2,4]}",
        GoToMeta(metatype="GOTO", scope=Scope.GONGAN, label="KAWITAN_ANGSEL", from_beat=None, passes=[2, 4]),
    ],
    [
        "{GOTO label=END_PENGAWAK, passes=3}",
        GoToMeta(metatype="GOTO", scope=Scope.GONGAN, label="END_PENGAWAK", from_beat=None, passes=[3]),
    ],
    [
        "{GOTO PENGAWAK_ANGSEL2, passes=[6, 12]}",
        GoToMeta(metatype="GOTO", scope=Scope.GONGAN, label="PENGAWAK_ANGSEL2", from_beat=None, passes=[6, 12]),
    ],
    [
        "{KEMPLI status=off, beats=[14,15,16]}",
        KempliMeta(metatype="KEMPLI", scope=Scope.GONGAN, status=MetaDataSwitch.OFF, beats=[14, 15, 16]),
    ],
    [
        "{KEMPLI status=on, beat=1}",
        KempliMeta(metatype="KEMPLI", scope=Scope.GONGAN, status=MetaDataSwitch.ON, beats=[1]),
    ],
    ["{KEMPLI off beats=14}", KempliMeta(metatype="KEMPLI", scope=Scope.GONGAN, status=MetaDataSwitch.OFF, beats=[14])],
    ["{LABEL name=D}", LabelMeta(metatype="LABEL", scope=Scope.GONGAN, name="D", beat=1)],
    ["{LABEL END_PENGAWAK}", LabelMeta(metatype="LABEL", scope=Scope.GONGAN, name="END_PENGAWAK", beat=1)],
    ["{PART name=batel}", PartMeta(metatype="PART", scope=Scope.GONGAN, name="batel")],
    ['{PART name="Pengecet part 2"}', PartMeta(metatype="PART", scope=Scope.GONGAN, name="Pengecet part 2")],
    ["{PART batel}", PartMeta(metatype="PART", scope=Scope.GONGAN, name="batel")],
    ["{REPEAT count=5}", RepeatMeta(metatype="REPEAT", scope=Scope.GONGAN, count=5)],
    ["{REPEAT 3}", RepeatMeta(metatype="REPEAT", scope=Scope.GONGAN, count=3)],
    [
        "{SEQUENCE value=[K_REGULAR, K_ANGSEL1, K_ANGSEL1, K_ANGSEL2, K_REGULAR, K_ANGSEL2, K_REGULAR, K_ANGSEL3, K_REGULAR, K_REGULAR, K_FINAL]}",
        SequenceMeta(
            metatype="SEQUENCE",
            scope=Scope.GONGAN,
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
        SequenceMeta(
            metatype="SEQUENCE",
            scope=Scope.GONGAN,
            value=["PENG1", "PENG2", "PENG1", "PENG2", "PENG3", "PENG4", "PENG3", "PENG4", "PENG1", "PENG2", "FINAL"],
        ),
    ],
    [
        '{SUPPRESS positions=["gangsa p", "gangsa s"], beats=[2,3,4,5,6,7,8], passes=[1, 2,3]}',
        SuppressMeta(
            metatype="SUPPRESS",
            scope=Scope.GONGAN,
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
        SuppressMeta(
            metatype="SUPPRESS",
            scope=Scope.GONGAN,
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
        TempoMeta(metatype="TEMPO", scope=Scope.GONGAN, value=100, first_beat=1, beat_count=8, passes=[2]),
    ],
    [
        "{TEMPO value=100, first_beat=1, beat_count=0}",
        TempoMeta(metatype="TEMPO", scope=Scope.GONGAN, value=100, first_beat=1, beat_count=0, passes=[-1]),
    ],
    [
        "{TEMPO 100 first_beat=1, beat_count=8, passes=3}",
        TempoMeta(metatype="TEMPO", scope=Scope.GONGAN, value=100, first_beat=1, beat_count=8, passes=[3]),
    ],
    [
        "{TEMPO value=47, passes=[1,2], first_beat=5, beat_count=3}",
        TempoMeta(metatype="TEMPO", scope=Scope.GONGAN, value=47, first_beat=5, beat_count=3, passes=[1, 2]),
    ],
    [
        "{VALIDATION ignore=[kempyung], scope=SCORE}",
        ValidationMeta(metatype="VALIDATION", scope=Scope.SCORE, beats=[], ignore=[ValidationProperty.KEMPYUNG]),
    ],
    [
        '{VALIDATION ["beat-duration"]}',
        ValidationMeta(metatype="VALIDATION", scope=Scope.GONGAN, beats=[], ignore=[ValidationProperty.BEAT_DURATION]),
    ],
    ["{WAIT seconds=3}", WaitMeta(metatype="WAIT", scope=Scope.GONGAN, seconds=3.0, after=True)],
    ["{WAIT 2.25}", WaitMeta(metatype="WAIT", scope=Scope.GONGAN, seconds=2.25, after=True)],
]


@pytest.mark.parametrize("metanotation, expected", metadata)
def test_parse_metadata(metanotation, expected, notation_grammar_model):
    parsed = _parse_notation("metadata\t" + metanotation + "\n", notation_grammar_model)
    assert parsed["gongans"][0]["metadata"][0].data == expected
