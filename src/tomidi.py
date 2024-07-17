import json
import os
from collections import defaultdict
from os import path

import pandas as pd
from mido import Message, MetaMessage, MidiFile, MidiTrack, bpm2tempo, tempo2bpm
from more_itertools import flatten

from notation_settings import BALIMUSIC4_TO_MIDI, TO_PIANO, MetaData, Tempo

INSTRUMENTS = ["gangsa p", "gangsa s"]

BASE_NOTE_TIME = 24


def add_metadata(meta: MetaData, track: MidiTrack, meta_info: dict) -> dict:
    match meta.data.type:
        case "gongan":
            ...
        case "tempo":
            tempo = bpm2tempo(meta.data.bpm)
            meta_info[0].append(MetaMessage("set_tempo", tempo=tempo))
            meta_info["tempo"] = tempo
        case "tempo-change":
            if meta.data.steps == 0:
                meta_info[0].append(
                    MetaMessage("set_tempo", tempo=bpm2tempo(tempo2bpm(meta_info["tempo"]) * meta.data.factor))
                )
            else:
                stepfactor = meta.data.factor ** (1 / meta.data.steps)
                tempo = meta_info["tempo"]
                for i in range(1, meta.data.steps + 1):
                    tempo = (
                        bpm2tempo(tempo2bpm(tempo) * stepfactor)
                        if i < meta.data.steps
                        else bpm2tempo(tempo2bpm(meta_info["tempo"]) * meta.data.factor)
                    )
                    meta_info[i].append(MetaMessage("set_tempo", tempo=tempo))
                meta_info["tempo"] = tempo
        case "label":
            ...
        case "loop":
            ...
        case _:
            raise ValueError(f"Metadata value {meta.data.type} is not supported.")

    return meta_info


def generate_metadata(meta_info: dict, track: MidiTrack) -> None:
    for msg in meta_info[0]:
        print(msg)
        track.append(msg)
    for key in sorted([key for key in meta_info.keys() if isinstance(key, int)]):
        meta_info[key] = meta_info.get(key + 1, [])
    return meta_info


def notation_to_track(notation: list[list[str]], instrument: str, piano_version=False) -> MidiTrack:
    track = MidiTrack()
    track.append(MetaMessage("track_name", name=instrument, time=0))
    track.append(
        MetaMessage(
            "time_signature", numerator=4, denominator=4, clocks_per_click=36, notated_32nd_notes_per_beat=8, time=0
        )
    )
    time_since_last_note_end = 0
    meta_info = defaultdict(list)

    for identifier, beats in notation:
        if identifier == "metadata":
            meta_info = add_metadata(MetaData(data=json.loads(beats[0])), track, meta_info)
        else:
            for beat in beats:
                meta_info = generate_metadata(meta_info, track)
                for note in beat:
                    noteinfo = BALIMUSIC4_TO_MIDI.get(note, None)
                    if not noteinfo:
                        print(f"{beats} -> {beat} no info for '{note}'")
                    if noteinfo.note > 30:
                        track.append(
                            Message(
                                type="note_on",
                                channel=0,
                                note=TO_PIANO[noteinfo.note] if piano_version else noteinfo.note,
                                velocity=70,
                                time=time_since_last_note_end,
                            )
                        )
                        track.append(
                            Message(
                                type="note_off",
                                channel=0,
                                note=TO_PIANO[noteinfo.note] if piano_version else noteinfo.note,
                                velocity=70,
                                time=int(noteinfo.duration * BASE_NOTE_TIME),
                            )
                        )
                        time_since_last_note_end = int(noteinfo.rest_after * BASE_NOTE_TIME)
                    elif noteinfo.note == -1:
                        track[-1].time = int(noteinfo.duration * BASE_NOTE_TIME)
                        time_since_last_note_end += int(noteinfo.rest_after * BASE_NOTE_TIME)
                    elif noteinfo.note == 0:
                        time_since_last_note_end += int(noteinfo.duration * BASE_NOTE_TIME)
                    elif noteinfo.note == 1:
                        track[-1].time += int(noteinfo.duration * BASE_NOTE_TIME)
    return track


def create_midifiles(
    datapath: str, infilename: str, outfilename: str, piano_version=False, separate_files=False
) -> None:
    columns = ["tag"] + [str(i) for i in range(1, 33)]
    df = pd.read_csv(path.join(datapath, infilename), sep="\t", names=columns, skip_blank_lines=False, encoding="UTF-8")
    # Blank lines denote start of new gongan or system
    df.loc[df["tag"].isna(), "1"] = '{"type": "gongan"}'
    df.loc[df["tag"].isna(), "tag"] = "metadata"

    if not separate_files:
        mid = MidiFile(ticks_per_beat=96, type=1)

    for instrument in INSTRUMENTS:
        if separate_files:
            mid = MidiFile(ticks_per_beat=96, type=0)
        notation = df[df["tag"].isin([instrument, "metadata", ""])].to_dict(orient="tight")["data"]
        notation = [(line[0], [n for n in line[1:] if pd.notna(n)]) for line in notation]
        track = notation_to_track(notation, instrument, piano_version)
        mid.tracks.append(track)
        if separate_files:
            mid.save(os.path.join(datapath, outfilename.format(instrument=instrument)))
    if not separate_files:
        mid.save(os.path.join(datapath, outfilename.format(instrument="")))


DATAPATH = ".\\data\\cendrawasih"
FILENAMECSV = "Cendrawasih.csv"
MIDIFILENAME = "Cendrawasih {instrument}.mid"
# DATAPATH = ".\\data\\margapati"
# FILENAMECSV = "Margapati-UTF8.csv"
# MIDIFILENAME = "Margapati {instrument}.mid"

if __name__ == "__main__":
    PIANOVERSION = True
    SEPARATE_FILES = True
    create_midifiles(DATAPATH, FILENAMECSV, MIDIFILENAME, PIANOVERSION, separate_files=SEPARATE_FILES)
