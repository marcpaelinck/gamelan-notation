import os
from itertools import product
from typing import Any

from pydantic import BaseModel, ConfigDict

from src.common.constants import InstrumentType, Modifier, Pitch, Position, Stroke
from src.common.notes import Tone
from src.settings.classes import RunSettings
from src.settings.constants import InstrumentFields
from src.settings.font_to_valid_notes import (
    create_note_records as create_note_records_old,
)
from src.settings.settings import Settings


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
    stroke: Stroke
    note_value: float | None
    modifier: Modifier
    midinote: list[int]
    rootnote: str
    sample: str


# OPEN_STROKE_DURATION_1_ONLY = [(Pitch.DENGDING, None)]
# STROKE_NOTE_VALUE = {
#     Stroke.ABBREVIATED: (0.4, 0.6),
#     Stroke.MUTED: (0.25, 0.75),
#     Stroke.GRACE_NOTE: (0, 0),
#     Stroke.SILENCE: (0, 1),
# }

TREMOLO_NOTES = [
    Pitch.CUNG,
    Pitch.DE,
    Pitch.DENGDING,
    Pitch.GIR,
    Pitch.KA,
    Pitch.KUNG,
    Pitch.PAK,
    Pitch.PUR,
    Pitch.TONG,
    Pitch.TUT,
]


def create_note_records(run_settings: RunSettings) -> list[dict[str, Any]]:
    instrument_data = run_settings.data.instruments
    note_list = []
    durations = [1, 0.5, 0.25]

    for record in instrument_data:
        if record[InstrumentFields.GROUP] is not run_settings.instrumentgroup:
            continue
        instrumenttype = record[InstrumentFields.INSTRUMENTTYPE]
        position: Position = record[InstrumentFields.POSITION]
        tones = [
            tone
            for tone in record[InstrumentFields.TONES] + record[InstrumentFields.EXTENDED_TONES]
            # if tone not in OPEN_STROKE_DURATION_1_ONLY
        ]  # !!!!!!!!!!!!!!!
        strokes = record[InstrumentFields.STROKES]
        patterns = record[InstrumentFields.PATTERNS]
        rests = record[InstrumentFields.RESTS]

        # Strokes (OPEN, ABBREVIATED, MUTED)
        for tone, stroke, duration in product(tones, strokes, durations):
            note_list.append(
                ValidNote(
                    instrumenttype=instrumenttype,
                    position=position,
                    symbol="",
                    pitch=tone[0],
                    octave=tone[1],
                    stroke=stroke,
                    note_value=duration,
                    modifier=Modifier.NONE,
                    midinote=[127],
                    rootnote="",
                    sample="",
                ).model_dump()
            )

        # This is only for DENGDING
        # specialtones = [
        #     tone
        #     for tone in record[InstrumentFields.TONES] + record[InstrumentFields.EXTENDED_TONES]
        #     if tone in OPEN_STROKE_DURATION_1_ONLY
        # ]  # !!!!!!!!!!!!!!!
        # for tone in specialtones:
        #     note_list.append(
        #         ValidNote(
        #             instrumenttype=instrumenttype,
        #             position=position,
        #             symbol="",
        #             pitch=tone[0],
        #             octave=tone[1],
        #             stroke=Stroke.OPEN,
        #             note_value=1,
        #             modifier=Modifier.NONE,
        #             midinote=[127],
        #             rootnote="",
        #             sample="",
        #         ).model_dump()
        #     )

        # Patterns (only melodic notes, exclude DENGDING)
        for tone, pattern in product(tones, patterns):
            if (
                Tone(pitch=tone[0], octave=tone[1]).is_melodic()
                or (
                    tone[0]
                    in (
                        Pitch.BYONG,
                        Pitch.STRIKE,
                    )
                    and pattern in [Stroke.TREMOLO, Stroke.TREMOLO_ACCELERATING, Stroke.GRACE_NOTE]
                )
                or (
                    position is Position.KENDANG
                    and pattern in [Stroke.TREMOLO, Stroke.TREMOLO_ACCELERATING, Stroke.GRACE_NOTE]
                )
            ):  # !!!!!!!!!!!!!!!!
                note_list.append(
                    ValidNote(
                        instrumenttype=instrumenttype,
                        position=position,
                        symbol="",
                        pitch=tone[0],
                        octave=tone[1],
                        stroke=pattern,
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
                    pitch=Pitch.NONE,
                    octave=None,
                    stroke=rest,
                    note_value=duration,
                    modifier=Modifier.NONE,
                    midinote=[127],
                    rootnote="",
                    sample="",
                ).model_dump()
            )

    return note_list


fields = [
    "instrumenttype",
    "position",
    "pitch",
    "octave",
    "stroke",
    "note_value",
]


def same(rec_1, rec_2):
    return all(rec_1[field] == rec_2[field] for field in fields)


def duplicates(records: list[dict[str, Any]]):
    shorts = [
        (tuple((k, v) for k, v in record.items()), tuple((k, v) for k, v in record.items() if k in fields))
        for record in records
    ]
    uniques = set(s[1] for s in shorts)
    uniques_tuples = [(unique, [short[0] for short in shorts if short[1] == unique]) for unique in uniques]

    for unique in uniques_tuples:
        if len(unique[1]) > 1:
            print(", ".join(f"{field[0]}:{field[1]}" for field in unique[0]))
            for long in unique[1]:
                print("     " + ", ".join(f"{field[0]}:{field[1]}" for field in long))


def dump(records: list[dict[str, Any]], file: str):
    with open(os.path.join("./data", file), "w", encoding="utf-8") as out:
        for nr, record in enumerate(records):
            if nr == 0:
                out.write("\t".join(key for key in record.keys()) + "\n")
            out.write("\t".join(str(val) for val in record.values()) + "\n")


def compare():
    run_settings = Settings.get()
    note_records = create_note_records(run_settings)
    note_records_old = create_note_records_old(run_settings)
    note_records_old = [r | {"note_value": r["duration"] + r["rest_after"]} for r in note_records_old]
    dump(note_records, "new.tsv")
    dump(note_records_old, "old.tsv")

    # new vs old
    match_n = []
    nonmatch_n = []
    match_o = []
    nonmatch_o = []
    for rec_n in note_records:
        rec_o = next((n for n in note_records_old if same(n, rec_n)), None)
        if rec_o:
            match_n.append(rec_n)
        else:
            nonmatch_n.append(rec_n)
    print(f"new: {len(note_records)}, matched: {len(match_n)}, unmatched: {len(nonmatch_n)}")
    print(nonmatch_n[:10])

    for rec_o in note_records_old:
        rec_n = next((n for n in note_records if same(n, rec_o)), None)
        if rec_n:
            match_o.append(rec_o)
        else:
            nonmatch_o.append(rec_o)
    print(f"old: {len(note_records_old)}, matched: {len(match_o)}, unmatched: {len(nonmatch_o)}")
    print(nonmatch_o[:10])
    dump(nonmatch_n, "nomatch_new.tsv")
    dump(nonmatch_o, "nomatch_old.tsv")

    # duplicates(note_records)


if __name__ == "__main__":
    compare()
