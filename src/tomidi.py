import json
import os
from collections import defaultdict
from dataclasses import dataclass
from enum import Enum
from os import path

import numpy as np
import pandas as pd
from mido import Message, MetaMessage, MidiFile, MidiTrack, bpm2tempo, tempo2bpm
from more_itertools import flatten

from notation_settings import (
    BALIMUSIC4_TO_MIDI,
    TO_PIANO,
    Beat,
    FlowInfo,
    GoTo,
    Instrument,
    Label,
    MetaData,
    Score,
    System,
    Tempo,
)


class InstrumentType(Enum):
    GANGSA_P = "gangsa p"
    GANGSA_S = "gangsa s"


@dataclass
class MetaInfo:
    bpm: int = 0


INSTRUMENTS = ["gangsa p", "gangsa s"]

BASE_NOTE_TIME = 24


# meta_info[0].append(MetaMessage("set_tempo", tempo=tempo))


def generate_metadata(meta_info: dict, track: MidiTrack) -> dict:
    for msg in meta_info[0]:
        print(msg)
        track.append(msg)
    for key in sorted([key for key in meta_info.keys() if isinstance(key, int)]):
        meta_info[key] = meta_info.get(key + 1, [])
    return meta_info


def notation_to_track(score: Score, instrument: str, piano_version=False) -> MidiTrack:
    def reset_score():
        for system in score.systems:
            for beat in system.beats:
                beat._pass_ = 0

    track = MidiTrack()
    track.append(MetaMessage("track_name", name=instrument, time=0))
    track.append(
        MetaMessage(
            "time_signature", numerator=4, denominator=4, clocks_per_click=36, notated_32nd_notes_per_beat=8, time=0
        )
    )

    time_since_last_note_end = 0

    current_bpm = 0
    reset_score()
    beat = score.systems[0].beats[0]
    while beat:
        if beat.bpm != current_bpm:
            track.append(MetaMessage("set_tempo", tempo=bpm2tempo(beat.bpm)))
            current_bpm = beat.bpm
        for note in beat.notes.get(instrument, []):
            if note.note > 30:
                track.append(
                    Message(
                        type="note_on",
                        channel=0,
                        note=TO_PIANO[note.note] if piano_version else note.note,
                        velocity=70,
                        time=time_since_last_note_end,
                    )
                )
                track.append(
                    Message(
                        type="note_off",
                        channel=0,
                        note=TO_PIANO[note.note] if piano_version else note.note,
                        velocity=70,
                        time=int(note.duration * BASE_NOTE_TIME),
                    )
                )
                time_since_last_note_end = int(note.rest_after * BASE_NOTE_TIME)
            elif note.note == -1:
                # Modify duration of previous note
                track[-1].time = int(note.duration * BASE_NOTE_TIME)
                time_since_last_note_end += int(note.rest_after * BASE_NOTE_TIME)
            elif note.note == 0:
                # Silcence: increment time since last note ended
                time_since_last_note_end += int(note.duration * BASE_NOTE_TIME)
            elif note.note == 1:
                # Note duration extension: add duration to last note
                track[-1].time += int(note.duration * BASE_NOTE_TIME)

        beat._pass_ += 1
        beat = beat.goto.get(beat._pass_, beat.next)

    return track


def create_midifiles(score, outfilepath: str, piano_version=False, separate_files=False) -> None:
    columns = ["tag"] + [str(i) for i in range(1, 33)]
    if not separate_files:
        mid = MidiFile(ticks_per_beat=96, type=1)

    for instrument in INSTRUMENTS:
        if separate_files:
            mid = MidiFile(ticks_per_beat=96, type=0)
        track = notation_to_track(score, instrument, piano_version)
        mid.tracks.append(track)
        if separate_files:
            mid.save(outfilepath.format(instrument=instrument))
    if not separate_files:
        mid.save(outfilepath.format(instrument=""))


def apply_metadata(metadata: list[MetaData], system: System, flowinfo: FlowInfo) -> None:
    def process_goto(system: System, goto: MetaData) -> None:
        for rep in goto.data.passes:
            system.beats[goto.data.beat_seq].goto[rep] = flowinfo.labels[goto.data.label]

    for meta in metadata:
        match meta.data:
            case Tempo():
                start_beat_seq = meta.data.first_beat_seq
                if meta.data.beats == 0:
                    # immediate bpm change
                    for beat in system.beats[start_beat_seq:]:
                        beat.bpm = beat.next_bpm = meta.data.bpm
                else:
                    # gradual bpm change over meta.data.beats beats.
                    # first bpm change is after first beat.
                    end_beat_seq = start_beat_seq + meta.data.beats
                    start_bpm = system.beats[start_beat_seq].next_bpm
                    step_increment = (meta.data.bpm - start_bpm) / meta.data.beats
                    # Gradually increase bpm for given range of beats
                    bpm = start_bpm
                    for beat in system.beats[start_beat_seq:]:
                        bpm = bpm + (step_increment if beat in system.beats[start_beat_seq:end_beat_seq] else 0)
                        beat.next_bpm = bpm
                    for prev_beat, next_beat in zip(system.beats, system.beats[1:]):
                        next_beat.bpm = prev_beat.next_bpm
            case Label():
                # Add the label to flowinfo
                flowinfo.labels[meta.data.label] = system.beats[meta.data.beat_seq]
                # Process any GoTo pointing to this label
                goto: MetaData
                for sys, goto in flowinfo.gotos[meta.data.label]:
                    process_goto(sys, goto)
            case GoTo():
                if flowinfo.labels.get(meta.data.label, None):
                    process_goto(system, meta)
                else:
                    # Label not yet encountered: store GoTo obect in flowinfo
                    flowinfo.gotos[meta.data.label].append((system, meta))
            case _:
                raise ValueError(f"Metadata value {meta.data.type} is not supported.")
    return


SYSTEM_LAST = "system_last"
METADATA = "metadata"
COMMENT = "comment"


def create_score(datapath: str, infilename: str, title: str) -> Score:
    columns = ["tag"] + ["BEAT" + str(i) for i in range(1, 33)]
    df = pd.read_csv(path.join(datapath, infilename), sep="\t", names=columns, skip_blank_lines=False, encoding="UTF-8")
    df["id"] = df.index
    # Drop all empty columns
    df.dropna(how="all", axis=1, inplace=True)
    # Number the systems: blank lines denote start of new system. Then delete blank lines.
    df["sysnr"] = df["tag"].isna().cumsum()[~df["tag"].isna()]
    # Reshape dataframe so that there is one beat per row. Column "BEAT" will contain the beat content.
    df = pd.wide_to_long(df, ["BEAT"], i=["sysnr", "tag", "id"], j="beat_nr").reset_index(inplace=False)
    df = df[~df["BEAT"].isna()]
    df["sysnr"] = df["sysnr"].astype("int16")

    # convert to list of systems, each system containing optional metadata and a list of instrument parts.
    df_dict = df.groupby(["sysnr", "beat_nr", "tag"])["BEAT"].apply(lambda g: g.values.tolist()).to_dict()
    # Create notation dict that is grouped by system and beat
    notation = defaultdict(lambda: defaultdict(lambda: defaultdict(list)))
    for (sysnr, beat_nr, tag), beat in df_dict.items():
        notation[sysnr][beat_nr][tag] = beat

    # TODO: extend all systems to contain all instruments
    score = Score(title=title)
    beats = []
    metadata = []
    flowinfo = FlowInfo()
    for sys_id, sys_info in notation.items():
        for beat_nr, beat_info in sys_info.items():
            # Create the beat and add it to the list of beats
            new_beat = Beat(
                id=f"{int(sys_id)}-{beat_nr}",
                notes=(
                    notes := {
                        tag: [BALIMUSIC4_TO_MIDI[note] for note in notes[0]]
                        for tag, notes in beat_info.items()
                        if tag not in [METADATA, COMMENT]
                    }
                ),
                bpm=(bpm := score.systems[-1].beats[-1].next_bpm if score.systems else 0),
                next_bpm=bpm,
                duration=sum(note.duration for note in list(notes.values())[0]),
            )
            prev_beat = beats[-1] if beats else score.systems[-1].beats[-1] if score.systems else None
            if prev_beat:
                prev_beat.next = new_beat
            beats.append(new_beat)

            for meta in beat_info.get(METADATA, []):
                metadata.append(MetaData(data=json.loads(meta)))

        # Create a new system
        if beats:
            system = System(id=int(sys_id), beats=beats)
            score.systems.append(system)
            apply_metadata(metadata, system, flowinfo)
            metadata = []
            beats = []

    return score


DATAPATH = ".\\data\\cendrawasih"
FILENAMECSV = "Cendrawasih.csv"
MIDIFILENAME = "Cendrawasih {instrument}.mid"
# DATAPATH = ".\\data\\margapati"
# FILENAMECSV = "Margapati-UTF8.csv"
# MIDIFILENAME = "Margapati {instrument}.mid"


if __name__ == "__main__":
    PIANOVERSION = True
    SEPARATE_FILES = False
    score = create_score(DATAPATH, FILENAMECSV, FILENAMECSV)
    outfilepath = os.path.join(DATAPATH, MIDIFILENAME)
    create_midifiles(score, outfilepath, piano_version=PIANOVERSION, separate_files=SEPARATE_FILES)
