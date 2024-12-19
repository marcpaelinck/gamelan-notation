import pytest

from src.common.classes import Beat, Gongan, Note, Score
from src.common.constants import Duration, Pitch, Position, Stroke
from src.common.metadata_classes import GonganType, ValidationProperty
from src.notation2midi.score_validation import ScoreValidator


@pytest.fixture
def sample_score():
    # Create a sample score with necessary settings
    class Settings:
        class Options:
            class NotationToMidi:
                autocorrect = True
                detailed_validation_logging = True

            notation_to_midi = NotationToMidi()
            notation = NotationToMidi()

        options = Options()

    return Score(settings=Settings())


@pytest.fixture
def sample_gongan():
    # Create a sample gongan with necessary attributes
    gongan = Gongan(
        gongantype=GonganType.REGULAR,
        beats=[
            Beat(
                full_id="1",
                duration=4,
                staves={
                    Position.PEMADE_POLOS: [
                        Note(pitch=Pitch.C, octave=4, stroke=Stroke.OPEN, duration=1, rest_after=0)
                    ],
                    Position.PEMADE_SANGSIH: [
                        Note(pitch=Pitch.D, octave=4, stroke=Stroke.OPEN, duration=1, rest_after=0)
                    ],
                },
                validation_ignore=[],
            )
        ],
    )
    return gongan


def test_incorrect_kempyung(sample_score, sample_gongan):
    validator = ScoreValidator(sample_score)
    invalids, corrected, ignored = validator._incorrect_kempyung(sample_gongan, autocorrect=True)

    assert len(invalids) == 1
    assert len(corrected) == 1
    assert len(ignored) == 0

    # Check the content of the invalids and corrected lists
    assert "BEAT 1" in invalids[0]
    assert "PEMADE_POLOS" in invalids[0]
    assert "PEMADE_SANGSIH" in invalids[0]

    assert "BEAT 1" in corrected[0]
    assert "PEMADE_POLOS" in corrected[0]
    assert "PEMADE_SANGSIH" in corrected[0]
