import pytest

from src.notation_constants import Note, SymbolValue
from src.score_validation import iskempyung

instrumentrange = [
    SymbolValue.DONG0,
    SymbolValue.DENG0,
    SymbolValue.DUNG0,
    SymbolValue.DANG0,
    SymbolValue.DING1,
    SymbolValue.DONG1,
    SymbolValue.DENG1,
    SymbolValue.DUNG1,
    SymbolValue.DANG1,
    SymbolValue.DING2,
    SymbolValue.DONG0_MUTED,
    SymbolValue.DENG0_MUTED,
    SymbolValue.DUNG0_MUTED,
    SymbolValue.DANG0_MUTED,
    SymbolValue.DING1_MUTED,
    SymbolValue.DONG1_MUTED,
    SymbolValue.DENG1_MUTED,
    SymbolValue.DUNG1_MUTED,
    SymbolValue.DANG1_MUTED,
    SymbolValue.DING2_MUTED,
]

data = [
    (SymbolValue.DONG0, SymbolValue.DANG0, True),
    (SymbolValue.DENG0, SymbolValue.DING1, True),
    (SymbolValue.DUNG0, SymbolValue.DONG1, True),
    (SymbolValue.DANG0, SymbolValue.DENG1, True),
    (SymbolValue.DING1, SymbolValue.DUNG1, True),
    (SymbolValue.DONG1, SymbolValue.DANG1, True),
    (SymbolValue.DENG1, SymbolValue.DING2, True),
    (SymbolValue.DUNG1, SymbolValue.DUNG1, True),
    (SymbolValue.DANG1, SymbolValue.DANG1, True),
    (SymbolValue.DING2, SymbolValue.DING2, True),
    (SymbolValue.DONG0_MUTED, SymbolValue.DANG0_MUTED, True),
    (SymbolValue.DONG0_MUTED, SymbolValue.DANG0, True),
    (SymbolValue.DONG0, SymbolValue.DANG0_MUTED, True),
    (SymbolValue.DUNG1, SymbolValue.DONG2, False),
]


@pytest.mark.parametrize("polos, sangsih, expected", data)
def test_iskempyung(polos: SymbolValue, sangsih: SymbolValue, expected: bool):
    assert iskempyung(polos, sangsih, instrumentrange) == expected
