import unittest
from unittest.mock import patch

from src.common.classes import Beat, Gongan, Measure, Note, Score
from src.common.constants import DEFAULT, Pitch, Position, Stroke
from src.common.metadata_classes import GonganType
from src.notation2midi.score_validation import ScoreValidator
from src.settings.constants import Yaml
from src.settings.settings import load_run_settings


def note(position: Position, pitch: Pitch, octave: int):
    return Note.get_note(position, pitch, octave, Stroke.OPEN, 1, 0)


class ScoreValidationTester(unittest.TestCase):

    @patch("src.settings.settings.SETTINGSFOLDER", "./tests/settings")
    def setUp(self):
        # Create a sample gongan with one incorrect beat (PEMADE and SANGSIH are the same) and one correct beat
        settings = load_run_settings({Yaml.COMPOSITION: "test-gongkebyar", Yaml.PART_ID: "full"})
        gongan = Gongan(
            id=1,
            gongantype=GonganType.REGULAR,
            beats=[
                Beat(
                    id=1,
                    gongan_id=1,
                    bpm_start=[],
                    bpm_end=[],
                    velocities_start=[],
                    velocities_end=[],
                    duration=10,
                    measures={
                        (P := Position.PEMADE_POLOS): Measure(
                            position=P,
                            passes={
                                DEFAULT: Measure.Pass(
                                    seq=DEFAULT,
                                    notes=[
                                        note(P, Pitch.DONG, 0),
                                        note(P, Pitch.DENG, 0),
                                        note(P, Pitch.DUNG, 0),
                                        note(P, Pitch.DANG, 0),
                                        note(P, Pitch.DING, 1),
                                        note(P, Pitch.DONG, 1),
                                        note(P, Pitch.DENG, 1),
                                        note(P, Pitch.DUNG, 1),
                                        note(P, Pitch.DANG, 1),
                                        note(P, Pitch.DING, 2),
                                    ],
                                )
                            },
                        ),
                        (S := Position.PEMADE_SANGSIH): Measure(
                            position=S,
                            passes={
                                DEFAULT: Measure.Pass(
                                    seq=DEFAULT,
                                    notes=[
                                        note(S, Pitch.DONG, 0),
                                        note(S, Pitch.DENG, 0),
                                        note(S, Pitch.DUNG, 0),
                                        note(S, Pitch.DANG, 0),
                                        note(S, Pitch.DING, 1),
                                        note(S, Pitch.DONG, 1),
                                        note(S, Pitch.DENG, 1),
                                        note(S, Pitch.DUNG, 1),
                                        note(S, Pitch.DANG, 1),
                                        note(S, Pitch.DING, 2),
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
