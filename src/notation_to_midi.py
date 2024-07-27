import json
import math
import os
from collections import defaultdict
from copy import copy
from dataclasses import dataclass
from os import path

import numpy as np
import pandas as pd
from mido import Message, MetaMessage, MidiFile, MidiTrack, bpm2tempo

from notation_classes import (
    Beat,
    Character,
    FlowInfo,
    Gongan,
    GoTo,
    InstrumentTag,
    Label,
    MetaData,
    MidiNote,
    Score,
    System,
    Tempo,
)
from notation_constants import DEFAULT, InstrumentGroup, InstrumentPosition, SymbolValue

BASE_NOTE_TIME = 24
MIDI_NOTES_DEF_FILE = "./settings/midinotes.csv"
BALIMUSIC4_DEF_FILE = "./settings/balimusic4font.csv"
TAGS_DEF_FILE = "./settings/instrumenttags.csv"
BALIMUSIC4_FONT_DICT = None
MIDI_NOTES_DICT = None
TAGS_TO_POSITIONS_DICT = None


def initialize_lookups(pianoversion: bool, instrumentgroup: InstrumentGroup) -> None:
    """Initializes dicts BALIMUSIC4_FONT_DICT and MIDI_NOTES_DICT

    Args:
        pianoversion (bool): if True, the midi values for a piano will be returned, otherwise the values for a gamelan orchestra.
        instrumentgroup (InstrumentGroup): The type of orchestra (e.g. gong kebyar, semar pagulingan)

    """
    global BALIMUSIC4_FONT_DICT, MIDI_NOTES_DICT, TAGS_TO_POSITIONS_DICT
    midinotes_obj = pd.read_csv(MIDI_NOTES_DEF_FILE, sep="\t").to_dict(orient="records")
    midinotes = [MidiNote.model_validate(note) for note in midinotes_obj]
    MIDI_NOTES_DICT = {
        (note.instrumenttype, note.notevalue): (note.pianomidi if pianoversion else note.midi)
        for note in midinotes
        if note.instrumentgroup == instrumentgroup
    }

    balifont_obj = pd.read_csv(BALIMUSIC4_DEF_FILE, sep="\t").to_dict(orient="records")
    balifont = [Character.model_validate(character) for character in balifont_obj]
    BALIMUSIC4_FONT_DICT = {character.symbol: character for character in balifont}

    tags_dict = pd.read_csv(TAGS_DEF_FILE, sep="\t").to_dict(orient="records")
    tags = [InstrumentTag.model_validate(record) for record in tags_dict]
    TAGS_TO_POSITIONS_DICT = {t.tag: t.positions for t in tags}


def notation_to_track(score: Score, position: InstrumentPosition) -> MidiTrack:
    """Generates the MIDI content for a single instrument position.

    Args:
        score (Score): The object model containing the notation.
        position (InstrumentPosition): the instrument position
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
    track.append(MetaMessage("track_name", name=position.value, time=0))
    # track.append(
    #     MetaMessage(
    #         "time_signature", numerator=4, denominator=4, clocks_per_click=36, notated_32nd_notes_per_beat=8, time=0
    #     )
    # )

    time_since_last_note_end = 0

    reset_pass_counters()
    beat = score.systems[0].beats[0]
    current_tempo = 0
    current_signature = 0
    while beat:
        beat._pass_ += 1
        # Set new not signature if the beat's system has a different beat length
        if new_signature := (
            round(score.systems[beat.sys_seq].beat_duration)
            if score.systems[beat.sys_seq].beat_duration != current_signature
            else None
        ):
            track.append(
                MetaMessage(
                    "time_signature",
                    numerator=new_signature,
                    denominator=4,
                    clocks_per_click=36,
                    notated_32nd_notes_per_beat=8,
                    time=time_since_last_note_end,
                )
            )
            time_since_last_note_end = 0
            current_signature = new_signature
        # Set new tempo
        if new_tempo := beat.get_changed_tempo(current_tempo):
            track.append(MetaMessage("set_tempo", tempo=bpm2tempo(new_tempo)))
            current_tempo = new_tempo
        # Process individual notes
        for note in beat.staves.get(position, []):
            if note.meaning.isnote:
                # Set ON and OFF messages for actual note
                track.append(
                    Message(
                        type="note_on",
                        channel=0,
                        note=MIDI_NOTES_DICT[position.instrumenttype, note.meaning],
                        velocity=100,
                        time=time_since_last_note_end,
                    )
                )
                track.append(
                    Message(
                        type="note_off",
                        channel=0,
                        note=MIDI_NOTES_DICT[position.instrumenttype, note.meaning],
                        velocity=70,
                        time=int(note.duration * BASE_NOTE_TIME),
                    )
                )
                time_since_last_note_end = int(note.rest_after * BASE_NOTE_TIME)
            elif note.meaning in [SymbolValue.MODIFIER_PREV1, SymbolValue.MODIFIER_PREV2]:
                # Should not occur because processed in create_score_object_model
                # track[-1].time = int(note.duration * BASE_NOTE_TIME)
                # time_since_last_note_end += int(note.rest_after * BASE_NOTE_TIME)
                raise ValueError(f"Unexpected note value {note.meaning}")
            elif note.meaning is SymbolValue.SILENCE:
                # Increment time since last note ended
                time_since_last_note_end += int(note.duration * BASE_NOTE_TIME)
            elif note.meaning is SymbolValue.EXTENSION:
                # Extension of note duration: add duration to last note
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
            case Gongan():
                # Meant for validation
                system.gongan = meta.data
            case _:
                raise ValueError(f"Metadata value {meta.data.type} is not supported.")
    return


METADATA = "metadata"
COMMENT = "comment"
NON_INSTRUMENT_TAGS = [METADATA, COMMENT]


def create_missing_staves(
    beat: Beat, all_positions: set[InstrumentPosition]
) -> dict[InstrumentPosition, list[Character]]:
    """Returns staves for missing positions, containing rests (silence) for the duration of the given beat.
    This ensures that positions that do not occur in all the systems will remain in sync.

    Args:
        beat (Beat): The beat that should be complemented.
        all_positions (set[InstrumentPosition]): List of all the positions that occur in the notation.

    Returns:
        dict[InstrumentPosition, list[Character]]: A dict with the generated staves.
    """
    if missing_positions := all_positions - set(beat.staves.keys()):
        rests = int(beat.duration)
        half_rests = int((beat.duration - rests) * 2)
        quarter_rests = int((beat.duration - rests - 0.5 * half_rests) * 4)
        notes = (
            [copy(BALIMUSIC4_FONT_DICT["-"])] * rests
            + [copy(BALIMUSIC4_FONT_DICT["µ"])] * half_rests
            + [copy(BALIMUSIC4_FONT_DICT["ª"])] * quarter_rests
        )
        return {position: notes for position in missing_positions}
    else:
        return dict()


def position_from_tag(tag: str) -> InstrumentPosition:
    if tag in TAGS_TO_POSITIONS_DICT:
        return TAGS_TO_POSITIONS_DICT[tag]
    else:
        raise ValueError(f"unrecognized instrument position {tag}")


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
    # Create enough column titles to accommodate all the notation columns, then read the notation
    columns = ["orig_tag"] + ["BEAT" + str(i) for i in range(1, 33)]
    df = pd.read_csv(path.join(datapath, infilename), sep="\t", names=columns, skip_blank_lines=False, encoding="UTF-8")
    df["id"] = df.index
    # insert a column with the normalized instrument/position names and duplicate rows that contain multiple positions
    df.insert(1, "tag", df["orig_tag"].apply(lambda val: TAGS_TO_POSITIONS_DICT.get(val, [])))
    df = df.explode("tag", ignore_index=True)
    df["tag"] = np.where(df["tag"].isnull(), df["orig_tag"], df["tag"])
    df.drop("orig_tag", axis="columns", inplace=True)
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

    # create a list of all instrument positions
    all_positions = set(df[~df["tag"].isin(NON_INSTRUMENT_TAGS)]["tag"].unique())

    score = Score(title=title, instrument_positions=all_positions)
    beats: list[Beat] = []
    metadata: list[MetaData] = []
    flowinfo = FlowInfo()
    for sys_id, sys_info in notation.items():
        for beat_nr, beat_info in sys_info.items():
            # create the staves
            staves = {
                tag: [copy(BALIMUSIC4_FONT_DICT[note]) for note in notechars[0]]
                for tag, notechars in beat_info.items()
                if tag not in NON_INSTRUMENT_TAGS
            }
            # Merge notes with negative valuewith previous note(s)
            for stave in staves.values():
                notes_to_remove = []
                for note in stave:
                    if note.meaning is SymbolValue.MODIFIER_PREV1:
                        prevnote = stave[stave.index(note) - 1]
                        prevnote.duration = note.duration
                        prevnote.rest_after = note.rest_after
                        notes_to_remove.append(note)
                    if note.meaning is SymbolValue.MODIFIER_PREV2:
                        prev1note = stave[stave.index(note) - 1]
                        prev1note.duration = note.rest_after
                        prev2note = stave[stave.index(note) - 2]
                        prev2note.duration = note.duration
                        prev2note.rest_after = 0
                        notes_to_remove.append(note)
                for note in notes_to_remove:
                    stave.remove(note)

            # Create the beat and add it to the list of beats
            new_beat = Beat(
                id=beat_nr,
                sys_id=sys_id,
                staves=staves,
                bpm_start={-1: (bpm := score.systems[-1].beats[-1].bpm_end[-1] if score.systems else 0)},
                bpm_end={-1: bpm},
                duration=sum(note.duration + note.rest_after for note in list(staves.values())[0]),
            )
            # Not all positions occur in each system.
            # Therefore we need to add blank staves (all rests) for missing positions.
            missing_staves = create_missing_staves(new_beat, score.instrument_positions)
            new_beat.staves.update(missing_staves)

            prev_beat = beats[-1] if beats else score.systems[-1].beats[-1] if score.systems else None
            if prev_beat:
                prev_beat.next = new_beat
            beats.append(new_beat)

            for meta in beat_info.get(METADATA, []):
                metadata.append(MetaData(data=json.loads(meta)))

        # Create a new system
        if beats:
            system = System(id=int(sys_id), beats=beats, beat_duration=beats[0].duration)
            score.systems.append(system)
            apply_metadata(metadata, system, flowinfo)
            metadata = []
            beats = []

    return score


def create_midifiles(score: Score, outfilepath: str, separate_files=False) -> None:
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

    for position in score.instrument_positions:
        if separate_files:
            mid = MidiFile(ticks_per_beat=96, type=0)
        track = notation_to_track(score, position)
        mid.tracks.append(track)
        if separate_files:
            mid.save(outfilepath.format(position=position.value))
    if not separate_files:
        mid.save(outfilepath.format(position=""))


def validate_model(score: Score) -> None:
    """Performs consistency checks and prints results.

    Args:
        score (Score): the score to analyze.
    """
    beat_not_pow2 = []
    beat_unequal_lengths = []

    for system in score.systems:
        for beat in system.beats:
            # Determine if the beat duration is a power of 2 (ignore kebyar)
            if system.gongan.kind != "kebyar" and 2 ** int(math.log2(beat.duration)) != beat.duration:
                beat_not_pow2.append((beat.full_id, beat.duration))
            # Check if the length of all staves in a beat are equal.
            if any(
                sum(note.duration + note.rest_after for note in notes) != beat.duration
                for notes in beat.staves.values()
            ):
                beat_unequal_lengths.append(
                    (
                        beat.full_id,
                        beat.duration,
                        [sum(note.duration + note.rest_after for note in notes) for notes in beat.staves.values()],
                    )
                )
    print(f"INCORRECT LENGTHS: {beat_not_pow2}")
    print(f"UNEQUAL LENGTHS: {beat_unequal_lengths}")


@dataclass
class Source:
    datapath: str
    csvfilename: str
    midifilename: str


CENDRAWASIH = Source(
    datapath=".\\data\\cendrawasih", csvfilename="Cendrawasih.csv", midifilename="Cendrawasih {position}.mid"
)
MARGAPATI = Source(
    datapath=".\\data\\margapati", csvfilename="Margapati-UTF8.csv", midifilename="Margapati {position}.mid"
)
GENDINGANAK2 = Source(
    datapath=".\\data\\test", csvfilename="Gending Anak-Anak.csv", midifilename="Gending Anak-Anak {position}.mid"
)
DEMO = Source(datapath=".\\data\\test", csvfilename="demo.csv", midifilename="Demo {position}.mid")


if __name__ == "__main__":
    source = GENDINGANAK2
    PIANOVERSION = True
    SEPARATE_FILES = False
    INSTRUMENTGROUP = InstrumentGroup.GONG_KEBYAR

    initialize_lookups(PIANOVERSION, INSTRUMENTGROUP)
    score = create_score_object_model(source.datapath, source.csvfilename, source.midifilename)
    validate_model(score)
    outfilepath = os.path.join(source.datapath, source.midifilename)
    create_midifiles(score, outfilepath, separate_files=SEPARATE_FILES)
