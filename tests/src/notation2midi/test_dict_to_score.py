import unittest
from enum import Enum, auto
from unittest.mock import MagicMock, patch

import pytest

import src.settings.settings
from src.common.classes import Beat, Gongan, Measure, Notation, Note, Score
from src.common.constants import (
    DEFAULT,
    DynamicLevel,
    InstrumentType,
    ParserTag,
    Pitch,
    Position,
    RuleType,
    Stroke,
)
from src.common.metadata_classes import (
    AutoKempyungMeta,
    DynamicsMeta,
    GonganMeta,
    GonganType,
    GoToMeta,
    KempliMeta,
    LabelMeta,
    MetaData,
    MetaDataSwitch,
    OctavateMeta,
    PartMeta,
    RepeatMeta,
    SequenceMeta,
    SuppressMeta,
    TempoMeta,
    ValidationMeta,
    WaitMeta,
)
from src.notation2midi.dict_to_score import DictToScoreConverter
from src.settings.constants import Yaml


class PositionNote:
    """Utility class to enable a compact notation of Note objects."""

    def __init__(self, position: Position):
        self.position = position

    def note(
        self,
        pitch: Pitch,
        octave: int = 1,
        stroke: Stroke = Stroke.OPEN,
        duration=1,
        rest_after=0,
        position: Position = None,
    ):
        return Note.get_note(
            position=position, pitch=pitch, octave=octave, stroke=stroke, duration=duration, rest_after=rest_after
        )

    @property
    def DING(self):
        return self.note(position=self.position, pitch=Pitch.DING)

    @property
    def DONG(self):
        return self.note(position=self.position, pitch=Pitch.DONG)

    @property
    def DONGMUTED(self):
        return self.note(position=self.position, pitch=Pitch.DONG, stroke=Stroke.MUTED)

    @property
    def DENG(self):
        return self.note(position=self.position, pitch=Pitch.DENG)

    @property
    def DUNG(self):
        return self.note(position=self.position, pitch=Pitch.DUNG)

    @property
    def DANG(self):
        return self.note(position=self.position, pitch=Pitch.DANG)

    @property
    def MUTEDSTRIKE(self):
        return self.note(position=self.position, pitch=Pitch.STRIKE, octave=None, stroke=Stroke.MUTED)

    @property
    def SILENCE(self):
        return self.note(
            position=self.position, pitch=Pitch.NONE, octave=None, stroke=Stroke.SILENCE, duration=0, rest_after=1
        )

    @property
    def EXTENSION(self):
        return self.note(position=self.position, pitch=Pitch.NONE, octave=None, stroke=Stroke.EXTENSION)


P = PositionNote(Position.PEMADE_POLOS)
S = PositionNote(Position.PEMADE_SANGSIH)
J = PositionNote(Position.JEGOGAN)
C = PositionNote(Position.CALUNG)


def create_beat(id: int = 1, content: dict[PositionNote, list[Note]] = None):
    measures = {
        pn.position: Measure(
            position=pn.position, passes={DEFAULT: Measure.Pass(seq=-1, notes=[note for note in measure])}
        )
        for pn, measure in content.items()
    }
    return Beat(
        id=id,
        gongan_id=1,
        bpm_start=60,
        bpm_end=60,
        velocities_start={},
        velocities_end={},
        duration=4,
        changes={},
        measures=measures,
        prev=None,
        next=None,
        validation_ignore=[],
    )


def get_notation():
    p = PositionNote(Position.PEMADE_POLOS)
    notation = {
        -1: {ParserTag.METADATA: [], ParserTag.COMMENTS: [], ParserTag.BEATS: []},
        1: {
            ParserTag.METADATA: [MetaData(data=KempliMeta(metatype="KEMPLI", status=MetaDataSwitch.OFF))],
            ParserTag.COMMENTS: ["Gongan 1"],
            ParserTag.BEATS: {
                1: {
                    (Position.PEMADE_POLOS): Measure(
                        position=Position.UGAL,
                        passes={-1: Measure.Pass(seq=-1, line=3, notes=[p.DING, p.DUNG, p.DENG, p.DANG])},
                    ),
                },
            },
        },
        2: {
            ParserTag.METADATA: [],
            ParserTag.COMMENTS: ["Gongan 2"],
            ParserTag.BEATS: {
                1: {
                    (Position.PEMADE_POLOS): Measure(
                        position=Position.UGAL,
                        passes={-1: Measure.Pass(seq=-1, line=3, notes=[p.DING, p.DONG, p.DENG, p.DUNG])},
                    ),
                },
            },
        },
    }
    return notation


class TestDictToScoreConverter(unittest.TestCase):

    @patch("src.settings.settings.SETTINGSFOLDER", "./tests/settings")
    def setUp(self):
        pass

    @patch("src.settings.settings.SETTINGSFOLDER", "./tests/settings")
    def get_converter_sp(self):
        settings = src.settings.settings.load_run_settings(
            notation={Yaml.COMPOSITION: "test-semarpagulingan", Yaml.PART_ID: "full"}
        )
        mock_notation = MagicMock(spec=Notation)
        mock_notation.settings = settings
        mock_notation.notation_dict = get_notation()
        return DictToScoreConverter(mock_notation)

    @patch("src.settings.settings.SETTINGSFOLDER", "./tests/settings")
    def get_converter_beat_at_end(self):
        settings = src.settings.settings.load_run_settings(
            notation={Yaml.COMPOSITION: "test_beat_at_end", Yaml.PART_ID: "full"}
        )
        mock_notation = MagicMock(spec=Notation)
        mock_notation.settings = settings
        mock_notation.notation_dict = get_notation()
        return DictToScoreConverter(mock_notation)

    def test_create_score(self):
        converter = self.get_converter_sp()
        score = converter.create_score()
        self.assertIsInstance(score, Score)
        self.assertEqual(
            converter.score.gongans[0].beats[0].measures[Position.PEMADE_POLOS],
            converter.notation.notation_dict[1][ParserTag.BEATS][1][Position.PEMADE_POLOS],
        )

    def test_get_all_positions(self):
        notation_dict = {
            1: {ParserTag.BEATS: {1: {Position.UGAL: [], Position.CALUNG: []}}},
            2: {ParserTag.BEATS: {1: {Position.JEGOGAN: [], Position.GONGS: []}}},
        }
        converter = self.get_converter_sp()
        positions = converter._get_all_positions(notation_dict)
        expected_positions = {Position.UGAL, Position.CALUNG, Position.JEGOGAN, Position.GONGS}
        self.assertEqual(positions, expected_positions)

    def test_has_kempli_beat(self):
        converter = self.get_converter_sp()
        score = converter.create_score()
        self.assertFalse(converter._has_kempli_beat(score.gongans[0]))
        self.assertTrue(converter._has_kempli_beat(score.gongans[1]))

    def test_move_beat_to_start1(self):
        # Test that the method is only called if beat_at_end is set.
        for getter in [self.get_converter_sp, self.get_converter_beat_at_end]:
            converter = getter()
            converter._move_beat_to_start = MagicMock(return_value=None)
            converter.create_score()
            if getter == self.get_converter_beat_at_end:
                converter._move_beat_to_start.assert_called_once()
            else:
                converter._move_beat_to_start.assert_not_called()

    def test_move_beat_to_start2(self):
        # Original score:
        #   gongan1: iuea
        #   gongan2: ioeu
        converter = self.get_converter_beat_at_end()
        converter.create_score()
        # Assert that the content of the first gongan was shifted by one note and that a silence
        # was added at the beginning.
        self.assertEqual(
            converter.score.gongans[0].beats[0].measures[Position.PEMADE_POLOS].passes[-1].notes,
            [P.SILENCE, P.DING, P.DUNG, P.DENG],
        )
        # Assert that the content of the second gongan was shifted by one note
        # and that its first beat now contains the last note of the previous beat.
        self.assertEqual(
            converter.score.gongans[1].beats[0].measures[Position.PEMADE_POLOS].passes[-1].notes,
            [P.DANG, P.DING, P.DONG, P.DENG],
        )
        # Assert that the second gongan has a kempli beat
        self.assertTrue(Position.KEMPLI in converter.score.gongans[1].beats[0].measures.keys())
        self.assertEqual(
            converter.score.gongans[1].beats[0].measures[Position.KEMPLI].passes[-1].notes,
            [k.MUTEDSTRIKE, k.EXTENSION, k.EXTENSION, k.EXTENSION],
        )
        # Assert that a new gongan was created containing the last note of the previous
        # gongan and a kempli beat.
        self.assertEqual(len(converter.score.gongans), 3)
        self.assertEqual(converter.score.gongans[2].beats[0].measures[Position.PEMADE_POLOS].passes[-1].notes, [P.DUNG])
        self.assertTrue(Position.KEMPLI in converter.score.gongans[2].beats[0].measures.keys())
        self.assertEqual(
            converter.score.gongans[2].beats[0].measures[Position.KEMPLI].passes[-1].notes,
            [k.MUTEDSTRIKE],
        )

    def test_create_rest_measure(self):
        converter = self.get_converter_beat_at_end()
        rest_measure = converter._create_rest_measure(Position.PEMADE_POLOS, Stroke.SILENCE, 2.5)
        self.assertEqual(len(rest_measure.passes[DEFAULT].notes), 3)
        self.assertEqual(rest_measure.passes[DEFAULT].notes[0].total_duration, 1)
        self.assertEqual(rest_measure.passes[DEFAULT].notes[1].total_duration, 1)
        self.assertEqual(rest_measure.passes[DEFAULT].notes[2].total_duration, 0.5)

    def test_create_rest_measures(self):

        converter = self.get_converter_sp()
        prev_beat = create_beat(
            {
                P: [P.DING, P.DONG, P.EXTENSION, P.EXTENSION],
                S: [S.DING, S.DONG, S.DONG, S.DONG],
                J: [J.DING, J.DONG, J.DING, J.SILENCE],
                C: [C.DING, C.DONG, C.DING, C.DONG],
            }
        )
        result = converter._create_rest_measures(
            prev_beat,
            positions=[
                Position.PEMADE_POLOS,
                Position.PEMADE_SANGSIH,
                Position.JEGOGAN,
                Position.CALUNG,
            ],
            duration=4,
            force_silence=[Position.CALUNG],
            pass_seq=DEFAULT,
        )
        self.assertEqual(
            result[Position.PEMADE_POLOS].passes[DEFAULT].notes, [P.EXTENSION, P.EXTENSION, P.EXTENSION, P.EXTENSION]
        )
        self.assertEqual(
            result[Position.PEMADE_SANGSIH].passes[DEFAULT].notes, [S.EXTENSION, S.EXTENSION, S.EXTENSION, S.EXTENSION]
        )
        self.assertEqual(result[Position.JEGOGAN].passes[DEFAULT].notes, [J.SILENCE, J.SILENCE, J.SILENCE, J.SILENCE])
        self.assertEqual(result[Position.CALUNG].passes[DEFAULT].notes, [C.SILENCE, C.SILENCE, C.SILENCE, C.SILENCE])

    metadata = [
        (
            DynamicsMeta(metatype="DYNAMICS", value=DynamicLevel.PIANISSIMO, first_beat=1),
            DynamicsMeta(metatype="DYNAMICS", value=DynamicLevel.FORTISSIMO, first_beat=2),
            ({1: {"value": DynamicLevel.PIANISSIMO}, 2: {"value": DynamicLevel.FORTISSIMO}}),
        ),
        (KempliMeta(metatype="KEMPLI", status=MetaDataSwitch.OFF, beats=[1])),
        (OctavateMeta(metatype="OCTAVATE", octaves=1, instrument=InstrumentType.UGAL)),
        ([TempoMeta(metatype="TEMPO", value=50, beat_count=1), TempoMeta(metatype="TEMPO", value=70, first_beat=2)]),
    ]

    metadata = [
        (GoToMeta(metatype="GOTO", label="LABEL1")),
        (SuppressMeta(metatype="SUPPRESS", positions=[Position.PEMADE_SANGSIH], beats=[2])),
        (WaitMeta(metatype="WAIT", seconds=2)),
    ]

    @pytest.mark.parametrize("metadata, expected", metadata)
    def test_apply_metadata(self):
        # Add test for _apply_metadata method
        beats = [
            create_beat(
                1,
                {
                    P: [P.DING, P.SILENCE, P.DONG, P.DING],
                    S: [S.DUNG, S.DENG, S.SILENCE, S.DUNG],
                    J: [J.DING, J.EXTENSION, J.EXTENSION, J.EXTENSION],
                    C: [C.DING, C.EXTENSION, C.DONG, C.EXTENSION],
                },
            ),
            create_beat(
                2,
                {
                    P: [P.SILENCE, P.DING, P.DONG, P.SILENCE],
                    S: [S.DENG, S.DUNG, S.SILENCE, S.DENG],
                    J: [J.DING, J.EXTENSION, J.EXTENSION, J.EXTENSION],
                    C: [C.DING, C.EXTENSION, C.DONG, C.EXTENSION],
                },
            ),
        ]
        gongan = Gongan(id=1, beats=beats, metadata=[LabelMeta(metatype="LABEL", name="LABEL1", beat=1)])

    def test_add_missing_measures(self):
        # Add test for _add_missing_measure method
        pass

    def test_extend_measure(self):
        # Add test for _extend_measure method
        pass

    def test_complement_shorthand_pokok_measure(self):
        # Add test for _complement_shorthand_pokok_measure method
        pass

    def test_reverse_kempyung(self):
        pass

    def test_process_goto(self):
        pass

    def test_process_sequences(self):
        pass

    def test_create_missing_measures(self):
        pass

    def test_init(self):
        # Test initialization with a mock Notation object
        pass
        # self.assertEqual(self.converter.notation, self.mock_notation)
        # self.assertEqual(
        #     self.converter.DEFAULT_VELOCITY, self.settings.midi.dynamics[self.settings.midi.default_dynamics]
        # )
        # self.assertEqual(self.converter.score.title, self.settings.notation.title)
        # self.assertEqual(self.converter.score.settings, self.mock_notation.settings)
        # self.assertEqual(
        #     self.converter.score.instrument_positions,
        #     self.converter._get_all_positions(self.mock_notation.notation_dict),
        # )


if __name__ == "__main__":
    unittest.main()
