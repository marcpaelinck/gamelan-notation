import unittest

from src.common.classes import Beat, Gongan, Measure, Score
from src.common.constants import DEFAULT, Position
from src.common.metadata_classes import GonganType
from src.notation2midi.score_validation import ScoreValidator
from src.settings.settings import Settings
from tests.conftest import BaseUnitTestCase
from tests.src.utils_for_tests import PositionNote


class ScoreValidationTester(BaseUnitTestCase):
    """Validator for the record to score parser"""

    # pylint: disable=protected-access

    def setUp(self):
        # Create a sample gongan with one incorrect beat (PEMADE and SANGSIH are the same) and one correct beat
        settings = Settings.get(notation_id="test-gongkebyar", part_id="full")
        P = PositionNote(Position.PEMADE_POLOS)
        S = PositionNote(Position.PEMADE_SANGSIH)

        gongan = Gongan(
            id=1,
            gongantype=GonganType.REGULAR,
            beats=[
                Beat(
                    id=1,
                    gongan_id=1,
                    bpm_start={},
                    bpm_end={},
                    velocities_start={},
                    velocities_end={},
                    duration=10,
                    measures={
                        P.position: Measure(
                            position=P.position,
                            all_positions=[P.position],
                            passes={
                                DEFAULT: Measure.Pass(
                                    seq=DEFAULT,
                                    notes=[
                                        P.DONG0,
                                        P.DENG0,
                                        P.DUNG0,
                                        P.DANG0,
                                        P.DING1,
                                        P.DONG1,
                                        P.DENG1,
                                        P.DUNG1,
                                        P.DANG1,
                                        P.DING2,
                                    ],
                                )
                            },
                        ),
                        S.position: Measure(
                            position=S.position,
                            all_positions=[S.position],
                            passes={
                                DEFAULT: Measure.Pass(
                                    seq=DEFAULT,
                                    notes=[
                                        S.DONG0,
                                        S.DENG0,
                                        S.DUNG0,
                                        S.DANG0,
                                        S.DING1,
                                        S.DONG1,
                                        S.DENG1,
                                        S.DUNG1,
                                        S.DANG1,
                                        S.DING2,
                                    ],
                                )
                            },
                        ),
                    },
                    validation_ignore=[],
                )
            ],
        )
        self.sample_gk_score = Score(title="Test", gongans=[gongan], settings=settings)

    def test_incorrect_kempyung(self):
        validator = ScoreValidator(self.sample_gk_score)
        invalids, corrected, ignored = validator._incorrect_kempyung(self.sample_gk_score.gongans[0], autocorrect=True)

        self.assertEqual(len(invalids), 0)
        self.assertEqual(len(corrected), 1)
        self.assertEqual(len(ignored), 0)

        # Check the content of the invalids and corrected lists
        self.assertIn("BEAT 1", corrected[0])
        self.assertIn("PEMADE", corrected[0])
        self.assertIn("P=[o,e,u,a,ioeuai<] S=[o,e,u,a,ioeuai<] -> S=[a,ioeuai<uai<]", corrected[0])
