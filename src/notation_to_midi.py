import json
import os
from collections import defaultdict
from copy import copy
from os import path

import numpy as np
import pandas as pd
from mido import Message, MetaMessage, MidiFile, MidiTrack, bpm2tempo

from src.notation_classes import (
    Beat,
    Character,
    Gongan,
    GoTo,
    InstrumentTag,
    Label,
    MetaData,
    MidiNote,
    Score,
    Source,
    System,
    Tempo,
)
from src.notation_constants import (
    ALL_PASSES,
    Duration,
    GonganType,
    InstrumentGroup,
    InstrumentPosition,
    MidiVersion,
    SymbolValue,
)
from src.score_validation import validate_score
from src.settings import BASE_NOTE_TIME, CENDRAWASIH
from src.settings_validation import validate_settings
from src.utils import (
    create_symbol_to_character_lookup,
    create_symbolvalue_to_midinote_lookup,
    create_tag_to_position_lookup,
)

SYMBOL_TO_CHARACTER_LOOKUP: dict[str, Character] = None
SYMBOLVALUE_TO_CHARACTER_LOOKUP: dict[(SymbolValue, Duration, Duration):Character]
SYMBOLVALUE_TO_MIDINOTE_LOOKUP: dict[tuple[InstrumentPosition, SymbolValue], MidiNote] = None
TAG_TO_POSITION_LOOKUP: dict[InstrumentTag, InstrumentPosition] = None


def initialize_constants(instrumentgroup: InstrumentGroup, version: MidiVersion) -> None:
    """Initializes lookup dicts and other constants

    Args:
        instrumentgroup (InstrumentGroup): The type of orchestra (e.g. gong kebyar, semar pagulingan)
        version (Version):  Used to define which midi mapping to use from the midinotes.csv file.

    """
    global SYMBOL_TO_CHARACTER_LOOKUP, SYMBOLVALUE_TO_CHARACTER_LOOKUP, SYMBOLVALUE_TO_MIDINOTE_LOOKUP, TAG_TO_POSITION_LOOKUP
    SYMBOL_TO_CHARACTER_LOOKUP = create_symbol_to_character_lookup()
    SYMBOLVALUE_TO_CHARACTER_LOOKUP = {
        (char.value, char.duration, char.rest_after): char for char in SYMBOL_TO_CHARACTER_LOOKUP.values()
    }
    SYMBOLVALUE_TO_MIDINOTE_LOOKUP = create_symbolvalue_to_midinote_lookup(instrumentgroup, version)
    TAG_TO_POSITION_LOOKUP = create_tag_to_position_lookup()


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

    track = MidiTrack()
    track.append(MetaMessage("track_name", name=position.value, time=0))
    # track.append(
    #     MetaMessage(
    #         "time_signature", numerator=4, denominator=4, clocks_per_click=36, notated_32nd_notes_per_beat=8, time=0
    #     )
    # )

    last_note_end_msg = None
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
            if not note.value.is_nonnote:
                midinote = SYMBOLVALUE_TO_MIDINOTE_LOOKUP[position.instrumenttype, note.value]
                # Set ON and OFF messages for actual note
                track.append(
                    Message(
                        type="note_on",
                        channel=midinote.channel,
                        note=midinote.midi,
                        velocity=100,
                        time=time_since_last_note_end,
                    )
                )
                track.append(
                    Message(
                        type="note_off",
                        channel=midinote.channel,
                        note=midinote.midi,
                        velocity=70,
                        time=int(note.duration * BASE_NOTE_TIME),
                    )
                )
                last_note_end_msg = track[-1]
                time_since_last_note_end = int(note.rest_after * BASE_NOTE_TIME)
            elif note.value in [SymbolValue.MODIFIER_PREV1, SymbolValue.MODIFIER_PREV2]:
                # Should not occur because processed in create_score_object_model
                # track[-1].time = int(note.duration * BASE_NOTE_TIME)
                # time_since_last_note_end += int(note.rest_after * BASE_NOTE_TIME)
                raise ValueError(f"Unexpected note value {note.value}")
            elif note.value is SymbolValue.SILENCE:
                # Increment time since last note ended
                time_since_last_note_end += int(note.duration * BASE_NOTE_TIME)
            elif note.value is SymbolValue.EXTENSION:
                # Extension of note duration: add duration to last note
                if last_note_end_msg:
                    last_note_end_msg.time += int(note.duration * BASE_NOTE_TIME)

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

    for meta in metadata:
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
                score.flowinfo.labels[meta.data.label] = system.beats[meta.data.beat_seq]
                # Process any GoTo pointing to this label
                goto: MetaData
                for sys, goto in score.flowinfo.gotos[meta.data.label]:
                    process_goto(sys, goto)
            case GoTo():
                if score.flowinfo.labels.get(meta.data.label, None):
                    process_goto(system, meta)
                else:
                    # Label not yet encountered: store GoTo obect in flowinfo
                    score.flowinfo.gotos[meta.data.label].append((system, meta))
            case Gongan():
                # Meant for validation
                system.gongantype = GonganType.from_value(meta.data.kind)
                for beat in system.beats:
                    if InstrumentPosition.KEMPLI in beat.staves:
                        beat.staves[InstrumentPosition.KEMPLI] = create_rest_stave(SymbolValue.SILENCE, beat.duration)
            case _:
                raise ValueError(f"Metadata value {meta.data.type} is not supported.")
    return


METADATA = "metadata"
COMMENT = "comment"
NON_INSTRUMENT_TAGS = [METADATA, COMMENT]


def create_rest_stave(resttype: SymbolValue, duration: float) -> list[Character]:
    """Creates a stave with rests of the given type for the given duration.
    If the duration is non-integer, the stave will also contain half and/or quarter rests.

    Args:
        resttype (SymbolValue): the type of rest (SILENCE or EXTENSION)
        duration (float): the duration, which can be non-integer.

    Returns:
        list[Character]: _description_
    """
    rest_count = int(duration)
    half_rest_count = int((duration - rest_count) * 2)
    quarter_rest_count = int((duration - rest_count - 0.5 * half_rest_count) * 4)
    rests = (
        [copy(SYMBOLVALUE_TO_CHARACTER_LOOKUP[resttype, 1, 0])] * rest_count
        + [SYMBOLVALUE_TO_CHARACTER_LOOKUP[resttype, 0.5, 0]] * half_rest_count
        + [SYMBOLVALUE_TO_CHARACTER_LOOKUP[resttype, 0.25, 0]] * quarter_rest_count
    )
    return rests


def create_missing_staves(beat: Beat, prevbeat: Beat, score: Score) -> dict[InstrumentPosition, list[Character]]:
    """Returns staves for missing positions, containing rests (silence) for the duration of the given beat.
    This ensures that positions that do not occur in all the systems will remain in sync.

    Args:
        beat (Beat): The beat that should be complemented.
        all_positions (set[InstrumentPosition]): List of all the positions that occur in the notation.

    Returns:
        dict[InstrumentPosition, list[Character]]: A dict with the generated staves.
    """

    if missing_positions := ((score.instrument_positions | {InstrumentPosition.KEMPLI}) - set(beat.staves.keys())):
        silence = SymbolValue.SILENCE
        extension = SymbolValue.EXTENSION
        prevnotes = {pos: (prevbeat.staves[pos][-1].value if prevbeat else silence) for pos in missing_positions}
        resttypes = {pos: silence if prevnote is silence else extension for pos, prevnote in prevnotes.items()}
        staves = {position: create_rest_stave(resttypes[position], beat.duration) for position in missing_positions}
        if InstrumentPosition.KEMPLI in staves.keys():
            kemplibeat = SYMBOLVALUE_TO_CHARACTER_LOOKUP[SymbolValue.TICK_1_PANGGUL, 1, 0]
            staves[InstrumentPosition.KEMPLI] = [kemplibeat] + create_rest_stave(
                SymbolValue.EXTENSION, beat.duration - 1
            )
        return staves
    else:
        return dict()


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
    all_positions = sorted([InstrumentPosition[pos] for pos in positions_str], key=lambda p: p.order)

    score = Score(
        source=source,
        midi_version=midiversion,
        instrument_positions=set(all_positions),
        balimusic4_font_dict=SYMBOL_TO_CHARACTER_LOOKUP,
        midi_notes_dict=SYMBOLVALUE_TO_MIDINOTE_LOOKUP,
    )
    beats: list[Beat] = []
    metadata: list[MetaData] = []
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

            # Merge notes with negative valuewith previous note(s)
            for stave in staves.values():
                stave_cpy = stave.copy()
                stave.clear()
                for note in stave_cpy:
                    if note.value is SymbolValue.MODIFIER_PREV1:
                        prevnote = stave.pop(-1)
                        stave.append(
                            prevnote.model_copy(update={"duration": note.duration, "rest_after": note.rest_after})
                        )
                    elif note.value is SymbolValue.MODIFIER_PREV2:
                        prev1note = stave.pop(-1)
                        prev2note = stave.pop(-1)
                        stave.append(prev2note.model_copy(update={"duration": note.duration}))
                        stave.append(prev1note.model_copy(update={"duration": note.rest_after}))
                    else:
                        stave.append(note)

            # Create the beat and add it to the list of beats
            new_beat = Beat(
                id=beat_nr,
                sys_id=sys_id,
                staves=staves,
                bpm_start={-1: (bpm := score.systems[-1].beats[-1].bpm_end[-1] if score.systems else 0)},
                bpm_end={-1: bpm},
                duration=max(sum(note.total_duration for note in notes) for notes in list(staves.values())),
            )
            # Not all positions occur in each system.
            # Therefore we need to add blank staves (all rests) for missing positions.
            prev_beat = beats[-1] if beats else score.systems[-1].beats[-1] if score.systems else None
            missing_staves = create_missing_staves(new_beat, prev_beat, score)
            new_beat.staves.update(missing_staves)
            # Updata all positions of score
            score.instrument_positions.update({pos for pos in missing_staves})

            if prev_beat:
                prev_beat.next = new_beat
            beats.append(new_beat)

            for meta in beat_info.get(METADATA, []):
                metadata.append(MetaData(data=json.loads(meta)))

        # Create a new system
        if beats:
            system = System(id=int(sys_id), beats=beats, beat_duration=beats[0].duration, metadata=metadata)
            score.systems.append(system)
            apply_metadata(metadata, system, score)
            metadata = []
            beats = []

    return score


def create_midifiles(score: Score, separate_files=False) -> None:
    """Generates the MIDI content and saves it to file.

    Args:
        score (Score): The object model.
        separate_files (bool, optional): If True, a separate file will be created for each instrument. Defaults to False.
    """
    outfilepathfmt = os.path.join(source.datapath, source.outfilefmt)
    if not separate_files:
        mid = MidiFile(ticks_per_beat=96, type=1)

    for position in sorted(score.instrument_positions, key=lambda x: x.order):
        if separate_files:
            mid = MidiFile(ticks_per_beat=96, type=0)
        track = notation_to_track(score, position)
        mid.tracks.append(track)
        if separate_files:
            mid.save(outfilepathfmt.format(position=position.value, ersion=score.midi_version, ext="mid"))
    if not separate_files:
        mid.save(outfilepathfmt.format(position="", version=score.midi_version, ext="mid"))


if __name__ == "__main__":
    source = CENDRAWASIH
    VERSION = MidiVersion.MULTIPLE_INSTR
    SEPARATE_FILES = False
    INSTRUMENTGROUP = InstrumentGroup.GONG_KEBYAR
    VALIDATE_ONLY = False
    AUTOCORRECT = True
    SAVE_CORRECTED_TO_FILE = True

    initialize_constants(INSTRUMENTGROUP, VERSION)
    validate_settings(list(SYMBOL_TO_CHARACTER_LOOKUP.values()))
    score = create_score_object_model(source, VERSION)
    validate_score(score=score, autocorrect=AUTOCORRECT, save_corrected=SAVE_CORRECTED_TO_FILE)
    if not VALIDATE_ONLY:
        create_midifiles(score, separate_files=SEPARATE_FILES)
