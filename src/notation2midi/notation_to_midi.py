import json
import os
from collections import defaultdict
from os import path

import numpy as np
import pandas as pd
from mido import MetaMessage, MidiFile, MidiTrack, bpm2tempo

from src.common.classes import (
    Beat,
    Gongan,
    GoTo,
    Kempli,
    Label,
    MetaData,
    Score,
    Source,
    System,
    Tempo,
)
from src.common.constants import (
    GonganType,
    InstrumentPosition,
    MetaDataStatus,
    MidiVersion,
    Note,
    Stroke,
)
from src.common.utils import (
    POSITION_TO_RANGE_LOOKUP,
    SYMBOL_TO_CHARACTER_LOOKUP,
    SYMBOLVALUE_TO_MIDINOTE_LOOKUP,
    TAG_TO_POSITION_LOOKUP,
    create_rest_stave,
    read_settings,
)
from src.notation2midi.font_specific_code import postprocess
from src.notation2midi.midi_track import MidiTrackX
from src.notation2midi.score_validation import add_missing_staves, validate_score
from src.notation2midi.settings import (
    ATTENUATION_SECONDS_AFTER_MUSIC_END,
    CENDRAWASIH,
    CENDRAWASIH5,
    COMMENT,
    MARGAPATI5,
    METADATA,
    MIDI_NOTES_DEF_FILE,
    NON_INSTRUMENT_TAGS,
    SINOMLADRANG,
)
from src.notation2midi.settings_validation import validate_settings


def notation_to_track(score: Score, position: InstrumentPosition) -> MidiTrack:
    """Generates the MIDI content for a single instrument position.

    Args:
        score (Score): The object model containing the notation.
        position (InstrumentPosition): the instrument position
        version (version): Used to define which midi mapping to use from the midinotes.csv file.

    Returns:
        MidiTrack: MIDI track for the instrument.
    """

    def reset_pass_counters():
        for system in score.systems:
            for beat in system.beats:
                beat._pass_ = 0

    track = MidiTrackX(score.source.font)
    track.append(MetaMessage("track_name", name=position.value, time=0))
    # track.append(
    #     MetaMessage(
    #         "time_signature", numerator=4, denominator=4, clocks_per_click=36, notated_32nd_notes_per_beat=8, time=0
    #     )
    # )

    reset_pass_counters()
    beat = score.systems[0].beats[0]
    # current_tempo = 0
    # current_signature = 0
    while beat:
        beat._pass_ += 1
        # Set new signature if the beat's system has a different beat length
        track.update_signature(score.systems[beat.sys_seq].beat_duration)
        # if new_signature := (
        #     round(score.systems[beat.sys_seq].beat_duration)
        #     if score.systems[beat.sys_seq].beat_duration != track.current_signature
        #     else None
        # ):
        # Set new tempo
        if new_bpm := beat.get_changed_tempo(track.current_bpm):
            # if position == InstrumentPosition.PEMADE_POLOS:
            # print(f"beat {beat.full_id}: tempo_change detectected from {track.current_bpm} to {new_bpm}")
            track.update_tempo(new_bpm or beat.get_bpm_start())
            # track.append(MetaMessage("set_tempo", tempo=bpm2tempo(new_tempo)))
            # current_tempo = new_tempo

        # Process individual notes
        for note in beat.staves.get(position, []):
            track.add_note(position, note)
        beat = beat.goto.get(beat._pass_, beat.next)

    return track


def apply_metadata(metadata: list[MetaData], system: System, score: Score) -> None:
    """Processes the metadata of a system into the object model.

    Args:
        metadata (list[MetaData]): The metadata to process.
        system (System): The system to which the metadata applies.
        score (score): The score
    """

    def process_goto(system: System, goto: MetaData) -> None:
        for rep in goto.data.passes:
            system.beats[goto.data.beat_seq].goto[rep] = score.flowinfo.labels[goto.data.label]

    haslabel = False
    for meta in sorted(metadata, key=lambda x: x.data._processingorder_):
        match meta.data:
            case Tempo():
                if meta.data.beats == 0:
                    # immediate tempo change.
                    system.beats[meta.data.first_beat_seq].tempo_changes.update(
                        {
                            pass_: Beat.TempoChange(new_tempo=meta.data.bpm, incremental=False)
                            for pass_ in meta.data.passes
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
                                for pass_ in meta.data.passes
                            }
                        )
                        steps -= 1

            case Label():
                # Add the label to flowinfo
                haslabel = True
                score.flowinfo.labels[meta.data.name] = system.beats[meta.data.beat_seq]
                # Process any GoTo pointing to this label
                goto: MetaData
                for sys, goto in score.flowinfo.gotos[meta.data.name]:
                    process_goto(sys, goto)
            case GoTo():
                if score.flowinfo.labels.get(meta.data.label, None):
                    process_goto(system, meta)
                else:
                    # Label not yet encountered: store GoTo obect in flowinfo
                    score.flowinfo.gotos[meta.data.label].append((system, meta))
            case Kempli():
                system.gongantype = meta.data.status
                if meta.data.status is MetaDataStatus.OFF:
                    for beat in system.beats:
                        if InstrumentPosition.KEMPLI in beat.staves:
                            beat.staves[InstrumentPosition.KEMPLI] = create_rest_stave(Stroke.SILENCE, beat.duration)
            case Gongan():
                # TODO: need to synchronize all instruments starting from next regular system
                system.gongantype = meta.data.kind
            case _:
                raise ValueError(f"Metadata value {meta.data.type} is not supported.")

    if haslabel:
        for beat in system.beats:
            if not beat.tempo_changes and beat.prev:
                beat.tempo_changes.update(beat.prev.tempo_changes)
        return


def create_score_object_model(source: Source, midiversion: MidiVersion) -> Score:
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
    filepath = path.join(source.datapath, source.infilename)
    df = pd.read_csv(filepath, sep="\t", names=columns, skip_blank_lines=False, encoding="UTF-8")
    df["id"] = df.index
    # insert a column with the normalized instrument/position names and duplicate rows that contain multiple positions
    df.insert(1, "tag", df["orig_tag"].apply(lambda val: TAG_TO_POSITION_LOOKUP.get(val, [])))
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
    positions_str = set(df[~df["tag"].isin(NON_INSTRUMENT_TAGS)]["tag"].unique())
    all_positions = sorted([InstrumentPosition[pos] for pos in positions_str], key=lambda p: p.sequence)

    score = Score(
        source=source,
        midi_version=midiversion,
        instrument_positions=set(all_positions),
        balimusic_font_dict=SYMBOL_TO_CHARACTER_LOOKUP,
        midi_notes_dict=SYMBOLVALUE_TO_MIDINOTE_LOOKUP,
        position_range_lookup=POSITION_TO_RANGE_LOOKUP,
    )
    beats: list[Beat] = []
    metadata: list[MetaData] = []
    comments: list[str] = []
    for sys_id, sys_info in notation.items():
        for beat_nr, beat_info in sys_info.items():
            # create the staves
            try:
                staves = {
                    tag: [SYMBOL_TO_CHARACTER_LOOKUP[note].model_copy() for note in notechars[0]]
                    for tag, notechars in beat_info.items()
                    if tag not in NON_INSTRUMENT_TAGS
                }
            except Exception as e:
                raise ValueError(f"unexpected character in beat {sys_id}-{beat_nr}: {e}")

            # Create the beat and add it to the list of beats
            new_beat = Beat(
                id=beat_nr,
                sys_id=sys_id,
                staves=staves,
                bpm_start={-1: (bpm := score.systems[-1].beats[-1].bpm_end[-1] if score.systems else 0)},
                bpm_end={-1: bpm},
                duration=max(
                    sum(char.total_duration for char in characters if char.note != Note.NONE)
                    for characters in list(staves.values())
                ),
            )
            prev_beat = beats[-1] if beats else score.systems[-1].beats[-1] if score.systems else None
            # Update the `next` pointer of the previous beat.
            if prev_beat:
                prev_beat.next = new_beat
                new_beat.prev = prev_beat
            beats.append(new_beat)

            for meta in beat_info.get(METADATA, []):
                metadata.append(MetaData(data=json.loads(meta)))

            for comment in beat_info.get(COMMENT, []):
                comments.append(comment)
        # Create a new system
        if beats:
            system = System(
                id=int(sys_id), beats=beats, beat_duration=beats[0].duration, metadata=metadata, comments=comments
            )
            score.systems.append(system)
            apply_metadata(metadata, system, score)
            metadata = []
            beats = []
            comments = []

    # Apply font-specific modifications
    postprocess(score)
    # Add kempli beats and blank staves for all other omitted instruments
    add_missing_staves(score)

    return score


def add_attenuation_time(tracks: list[MidiTrackX], seconds: int) -> None:
    max_ticks = max(track.total_tick_time() for track in tracks)
    for track in tracks:
        if track.total_tick_time() == max_ticks:
            track.extend_last_note(seconds)


def create_midifile(score: Score) -> None:
    """Generates the MIDI content and saves it to file.

    Args:
        score (Score): The object model.
        separate_files (bool, optional): If True, a separate file will be created for each instrument. Defaults to False.
    """
    outfilepathfmt = os.path.join(source.datapath, source.outfilefmt)
    mid = MidiFile(ticks_per_beat=96, type=1)

    for position in sorted(score.instrument_positions, key=lambda x: x.sequence):
        track = notation_to_track(score, position)
        mid.tracks.append(track)
    add_attenuation_time(mid.tracks, seconds=ATTENUATION_SECONDS_AFTER_MUSIC_END)
    mid.save(outfilepathfmt.format(position="", version=score.midi_version, ext="mid"))


if __name__ == "__main__":
    source = SINOMLADRANG
    VERSION = MidiVersion.MULTIPLE_INSTR
    # --------------------------
    VALIDATE_SETTINGS = True
    DETAILED_VALIDATION_LOGGING = False
    AUTOCORRECT = True
    SAVE_CORRECTED_TO_FILE = True
    # --------------------------
    CREATE_MIDIFILE = True

    read_settings(source, VERSION, MIDI_NOTES_DEF_FILE)
    if VALIDATE_SETTINGS:
        validate_settings(source)
    score = create_score_object_model(source, VERSION)
    validate_score(
        score=score,
        autocorrect=AUTOCORRECT,
        save_corrected=SAVE_CORRECTED_TO_FILE,
        detailed_logging=DETAILED_VALIDATION_LOGGING,
    )
    if CREATE_MIDIFILE:
        create_midifile(score)
