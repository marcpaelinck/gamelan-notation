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
    DEFAULT,
    INSTRUMENT,
    TO_PIANO,
    Beat,
    FlowInfo,
    GoTo,
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


BASE_NOTE_TIME = 24


def notation_to_track(score: Score, instrument: str, piano_version=False) -> MidiTrack:
    """Generates the MIDI content for a single instrument.

    Args:
        score (Score): The object model containing the notation.
        instrument (str): Instrument
        piano_version (bool, optional): If True, a version for standard piano is generated.
                                Otherwise a version for the gong kebyar instrument rack is created. Defaults to False.

    Returns:
        MidiTrack: MIDI track for the instrument.
    """

    def reset_pass_counters():
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

    reset_pass_counters()
    beat = score.systems[0].beats[0]
    current_tempo = 0
    while beat:
        beat._pass_ += 1
        if new_tempo := beat.get_changed_tempo(current_tempo):
            track.append(MetaMessage("set_tempo", tempo=bpm2tempo(new_tempo)))
            current_tempo = new_tempo
        for note in beat.notes.get(instrument, []):
            if note.note > 30:
                track.append(
                    Message(
                        type="note_on",
                        channel=0,
                        note=TO_PIANO[note.note] if piano_version else note.note,
                        velocity=100,
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

        beat = beat.goto.get(beat._pass_, beat.next)

    return track


def apply_metadata(metadata: list[MetaData], system: System, flowinfo: FlowInfo) -> None:
    """Processes the metadata of a system into the object model.

    Args:
        metadata (list[MetaData]): The metadata to process.
        system (System): The system to which the metadata applies.
        flowinfo (FlowInfo): Auxiliary object used to process "goto" statements. It keeps
                            track of the labels and "goto" statements that point to labels
                            that have not yet been encountered.
    """

    def process_goto(system: System, goto: MetaData) -> None:
        for rep in goto.data.passes:
            system.beats[goto.data.beat_seq].goto[rep] = flowinfo.labels[goto.data.label]

    for meta in metadata:
        match meta.data:
            case Tempo():
                if meta.data.beats == 0:
                    # immediate tempo change.
                    system.beats[meta.data.first_beat_seq].tempo_changes.update(
                        {
                            pass_: Beat.TempoChange(new_tempo=meta.data.bpm, incremental=False)
                            for pass_ in meta.data.passes or [DEFAULT]
                        }
                    )
                    # immediate bpm change
                else:
                    # Stepwise tempo change over meta.data.beats beats. The first tempo change is after first beat.
                    # This emulates a gradual tempo change.
                    beat = system.beats[meta.data.first_beat_seq]
                    steps = meta.data.beats
                    for _ in range(meta.data.beats):
                        beat = beat.next
                        if not beat:  # End of score. This should not happen unless notation error.
                            break
                        beat.tempo_changes.update(
                            {
                                pass_: Beat.TempoChange(new_tempo=meta.data.bpm, steps=steps, incremental=True)
                                for pass_ in meta.data.passes or [DEFAULT]
                            }
                        )
                        steps -= 1

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
NON_INSTRUMENT_TAGS = [METADATA, COMMENT]


def create_missing_staves(beat: Beat, all_instruments: set[INSTRUMENT]) -> dict[INSTRUMENT, str]:
    """Returns staves for missing instruments, containing rests (silence) for the duration of the given beat.
    This ensures that instruments that do not occur in all the systems will remain in sync.

    Args:
        beat (Beat): The beat that should be complemented.
        all_instruments (set[INSTRUMENT]): List of all the instruments that occur in the notation.

    Returns:
        dict[INSTRUMENT, str]: A dict with the generated staves.
    """
    if missing_instruments := all_instruments - set(beat.notes.keys()):
        rests = int(beat.duration)
        half_rests = int((beat.duration - rests) * 2)
        quarter_rests = int((beat.duration - rests - 0.5 * half_rests) * 4)
        notes = (
            [BALIMUSIC4_TO_MIDI["-"]] * rests
            + [BALIMUSIC4_TO_MIDI["µ"]] * half_rests
            + [BALIMUSIC4_TO_MIDI["ª"]] * quarter_rests
        )
        return {instrument: notes for instrument in missing_instruments}
    else:
        return dict()


def create_score_object_model(datapath: str, infilename: str, title: str) -> Score:
    """Creates an object model of the notation.
    This will simplify the generation of the MIDI file content.

    Args:
        datapath (str): path to the data folder
        infilename (str): name of the csv input file
        title (str): Title for the notation

    Returns:
        Score: Object model containing the notation information.
    """
    columns = ["tag"] + ["BEAT" + str(i) for i in range(1, 33)]
    df = pd.read_csv(path.join(datapath, infilename), sep="\t", names=columns, skip_blank_lines=False, encoding="UTF-8")
    df["id"] = df.index
    # Drop all empty columns
    df.dropna(how="all", axis=1, inplace=True)
    # Number the systems: blank lines denote start of new system. Then delete blank lines.
    df["sysnr"] = df["tag"].isna().cumsum()[~df["tag"].isna()] + 1
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

    # create a list of all instruments
    all_instruments = set(df[~df["tag"].isin(NON_INSTRUMENT_TAGS)]["tag"].unique())

    score = Score(title=title, instruments=all_instruments)
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
                        tag: [BALIMUSIC4_TO_MIDI[note] for note in notechars[0]]
                        for tag, notechars in beat_info.items()
                        if tag not in [METADATA, COMMENT]
                    }
                ),
                bpm_start={-1: (bpm := score.systems[-1].beats[-1].bpm_end[-1] if score.systems else 0)},
                bpm_end={-1: bpm},
                duration=sum(note.duration for note in list(notes.values())[0]),
            )
            # Not all instruments occur in each system.
            # Therefore we need to add blank staves (all rests) for missing instruments.
            missing_staves = create_missing_staves(new_beat, score.instruments)
            new_beat.notes.update(missing_staves)

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


def create_midifiles(score: Score, outfilepath: str, piano_version=False, separate_files=False) -> None:
    """Generates the MIDI content and saves it to file.

    Args:
        score (Score): The object model.
        outfilepath (str): Path to the destination folder.
        piano_version (bool, optional): If True, a version for standard piano is generated.
                                Otherwise a version for the gong kebyar instrument rack is created. Defaults to False.
        separate_files (bool, optional): If True, a separate file will be created for each instrument. Defaults to False.
    """
    if not separate_files:
        mid = MidiFile(ticks_per_beat=96, type=1)

    for instrument in score.instruments:
        if separate_files:
            mid = MidiFile(ticks_per_beat=96, type=0)
        track = notation_to_track(score, instrument, piano_version)
        mid.tracks.append(track)
        if separate_files:
            mid.save(outfilepath.format(instrument=instrument))
    if not separate_files:
        mid.save(outfilepath.format(instrument=""))


DATAPATH = ".\\data\\cendrawasih"
FILENAMECSV = "Cendrawasih.csv"
MIDIFILENAME = "Cendrawasih {instrument}.mid"
# DATAPATH = ".\\data\\margapati"
# FILENAMECSV = "Margapati-UTF8.csv"
# MIDIFILENAME = "Margapati {instrument}.mid"
# DATAPATH = ".\\data\\test"
# FILENAMECSV = "Gending Anak-Anak.csv"
# MIDIFILENAME = "Gending Anak-Anak {instrument}.mid"


if __name__ == "__main__":
    PIANOVERSION = True
    SEPARATE_FILES = False
    score = create_score_object_model(DATAPATH, FILENAMECSV, FILENAMECSV)
    outfilepath = os.path.join(DATAPATH, MIDIFILENAME)
    create_midifiles(score, outfilepath, piano_version=PIANOVERSION, separate_files=SEPARATE_FILES)
