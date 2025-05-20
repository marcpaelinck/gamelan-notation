# pylint: disable=missing-module-docstring, missing-class-docstring, missing-function-docstring, line-too-long, invalid-name

from src.common.constants import DEFAULT, Position
from src.notation2midi.execution import Score
from src.notation2midi.score_validation import ScoreValidationAgent
from src.settings.settings import Settings
from tests.conftest import BaseUnitTestCase
from tests.src.utils_for_tests import PositionNote, create_gongan


class ScoreValidationTester(BaseUnitTestCase):
    """Validator for the record to score parser"""

    # pylint: disable=protected-access

    def setUp(self):
        # Create a sample gongan with one incorrect beat (PEMADE and SANGSIH are the same) and one correct beat
        self.settings = Settings.get(notation_id="test-gongkebyar", part_id="full")
        P = PositionNote(Position.PEMADE_POLOS)
        S = PositionNote(Position.PEMADE_SANGSIH)

        # fmt: off
        gongan = create_gongan(
                    1,
                    {P.position: {DEFAULT: [[P.DONG0, P.DENG0, P.DUNG0, P.DANG0, P.DING1, P.DONG1, P.DENG1, P.DUNG1, P.DANG1, P.DING2]]},
                     S.position: {DEFAULT: [[S.DONG0, S.DENG0, S.DUNG0, S.DANG0, S.DING1, S.DONG1, S.DENG1, S.DUNG1, S.DANG1, S.DING2]]}
                    }
                )
        # fmt: on

        self.sample_gk_score = Score(title="Test", gongans=[gongan], settings=self.settings)

    def test_incorrect_kempyung(self):
        validator = ScoreValidationAgent(self.settings, self.sample_gk_score)
        invalids, corrected, ignored = validator._incorrect_kempyung(self.sample_gk_score.gongans[0], autocorrect=True)

        self.assertEqual(len(invalids), 0)
        self.assertEqual(len(corrected), 1)
        self.assertEqual(len(ignored), 0)

        # Check the content of the invalids and corrected lists
        self.assertIn("BEAT 1", corrected[0])
        self.assertIn("PEMADE", corrected[0])
        self.assertIn("P=[o,e,u,a,ioeuai<] S=[o,e,u,a,ioeuai<] -> S=[a,ioeuai<uai<]", corrected[0])
