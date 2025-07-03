from itertools import product
from typing import Any, Union

from pydantic import BaseModel, ConfigDict

from src.common.constants import (
    InstrumentType,
    Modifier,
    PatternType,
    Pitch,
    Position,
    Stroke,
)
from src.settings.classes import RunSettings
from src.settings.constants import EffectsFields, InstrumentFields


class ValidNote(BaseModel):
    # Class used to create notes with validated field values. Only int values may be None,
    # other values will raise an exception if missing, malformed or None (we use Pydantic to check this).
    # We don't use the Note class here to avoid circular references.
    model_config = ConfigDict(extra="forbid", frozen=True, revalidate_instances="always")

    instrumenttype: InstrumentType
    position: Position
    symbol: str
    pitch: Pitch
    octave: int | None
    effect: Union[Stroke, PatternType]
    note_value: float | None
    modifier: Modifier
    midinote: list[int]
    rootnote: str
    sample: str


def get_note_records(run_settings: RunSettings) -> list[dict[str, Any]]:
    instrument_data = [
        rec for rec in run_settings.data.instruments if rec[InstrumentFields.GROUP] is run_settings.instrumentgroup
    ]
    effect_dict = {rec[EffectsFields.EFFECT]: rec[EffectsFields.PITCHES] for rec in run_settings.data.effects}
    note_list = []
    durations = [1, 0.5, 0.25]

    for record in instrument_data:
        instrumenttype = record[InstrumentFields.INSTRUMENTTYPE]
        position: Position = record[InstrumentFields.POSITION]
        tones = [tone for tone in record[InstrumentFields.TONES] + record[InstrumentFields.EXTENDED_TONES]]
        strokes = record[InstrumentFields.STROKES]
        patterns = record[InstrumentFields.PATTERNS]
        rests = record[InstrumentFields.RESTS]

        # Strokes (OPEN, ABBREVIATED, MUTED)
        for (pitch, octave), stroke, duration in product(tones, strokes, durations):
            if not stroke in effect_dict or pitch in effect_dict[stroke]:
                note_list.append(
                    ValidNote(
                        instrumenttype=instrumenttype,
                        position=position,
                        symbol="",
                        pitch=pitch,
                        octave=octave,
                        effect=stroke,
                        note_value=duration,
                        modifier=Modifier.NONE,
                        midinote=[127],
                        rootnote="",
                        sample="",
                    ).model_dump()
                )

        # Patterns (only melodic notes, exclude DENGDING)
        for (pitch, octave), pattern in product(tones, patterns):
            if not pattern in effect_dict or pitch in effect_dict[pattern]:
                note_list.append(
                    ValidNote(
                        instrumenttype=instrumenttype,
                        position=position,
                        symbol="",
                        pitch=pitch,
                        octave=octave,
                        effect=pattern,
                        note_value=1,
                        modifier=Modifier.NONE,
                        midinote=[127],
                        rootnote="",
                        sample="",
                    ).model_dump()
                )

        # Rests
        for rest, duration in product(rests, durations):
            note_list.append(
                ValidNote(
                    instrumenttype=instrumenttype,
                    position=position,
                    symbol="",
                    pitch=rest,
                    octave=None,
                    effect=Stroke.NONE,
                    note_value=duration,
                    modifier=Modifier.NONE,
                    midinote=[127],
                    rootnote="",
                    sample="",
                ).model_dump()
            )

    return note_list
