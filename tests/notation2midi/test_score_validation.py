import pytest

from src.common.classes import Beat, Gongan, Measure, Note, Score
from src.common.constants import DEFAULT, Pitch, Position, Stroke
from src.common.metadata_classes import GonganType
from src.notation2midi.score_validation import ScoreValidator
from src.settings.constants import Yaml
from src.settings.settings import load_run_settings


def note(position: Position, pitch: Pitch, octave: int):
    return Note.get_note(position, pitch, octave, Stroke.OPEN, 1, 0)


@pytest.fixture
def sample_gk_score():
    # Create a sample gongan with one incorrect beat (PEMADE and SANGSIH are the same) and one correct beat
    settings = load_run_settings({Yaml.COMPOSITION: "sinomladrang-gk", Yaml.PART: "full"})
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
    return Score(title="Test", gongans=[gongan], settings=settings)


def test_incorrect_kempyung(sample_gk_score):

    validator = ScoreValidator(sample_gk_score)
    invalids, corrected, ignored = validator._incorrect_kempyung(sample_gk_score.gongans[0], autocorrect=True)

    assert len(invalids) == 0
    assert len(corrected) == 1
    assert len(ignored) == 0

    # Check the content of the invalids and corrected lists
    assert "BEAT 1" in corrected[0]
    assert "PEMADE" in corrected[0]
    assert "P=[o,e,u,a,ioeuai<] S=[o,e,u,a,ioeuai<] -> S=[a,ioeuai<uai<]" in corrected[0]
