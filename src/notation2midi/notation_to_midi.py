""" Creates a midi file based on a notation file.
    See ./data/README.md for more information about notation files and ./data/notation/test for an example of a notation file.

    Main method: convert_notation_to_midi()
"""

import json
import re
from collections import defaultdict

import numpy as np
import pandas as pd
from mido import MetaMessage, MidiFile

from src.common.classes import Beat, Gongan, RunSettings, Score
from src.common.constants import DEFAULT, InstrumentPosition, Pitch, Stroke
from src.common.metadata_classes import (
    GonganMeta,
    GoToMeta,
    KempliMeta,
    LabelMeta,
    MetaData,
    MetaDataSwitch,
    RepeatMeta,
    SilenceMeta,
    TempoMeta,
    ValidationMeta,
)
from src.common.utils import (
    POSITION_TO_RANGE_LOOKUP,
    SYMBOL_TO_NOTE_LOOKUP,
    SYMBOLVALUE_TO_MIDINOTE_LOOKUP,
    TAG_TO_POSITION_LOOKUP,
    create_rest_stave,
    read_settings,
)
from src.notation2midi.font_specific_code import postprocess
from src.notation2midi.midi_track import MidiTrackX
from src.notation2midi.score_validation import add_missing_staves, validate_score
from src.settings.settings import (
    ATTENUATION_SECONDS_AFTER_MUSIC_END,
    COMMENT,
    METADATA,
    NON_INSTRUMENT_TAGS,
    get_run_settings,
)
from src.settings.settings_validation import validate_settings


def notation_to_track(score: Score, position: InstrumentPosition) -> MidiTrackX:
    """Generates the MIDI content for a single instrument position.

    Args:
        score (Score): The object model containing the notation.
        position (InstrumentPosition): the instrument position

    Returns:
        MidiTrack: MIDI track for the instrument.
    """

    def reset_pass_counters():
        for gongan in score.gongans:
            for beat in gongan.beats:
                beat._pass_ = 0

    track = MidiTrackX(position)

    reset_pass_counters()
    beat = score.gongans[0].beats[0]
    while beat:
        beat._pass_ += 1
        # Set new tempo
        if new_bpm := beat.get_changed_tempo(track.current_bpm):
            track.update_tempo(new_bpm or beat.get_bpm_start())

        # Process individual notes. Check if there is an alternative stave for the current pass
        for note in beat.exceptions.get((position, beat._pass_), beat.staves.get(position, [])):
            track.add_note(position, note)
        beat = beat.goto.get(beat._pass_, beat.next)

    return track


def apply_metadata(metadata: list[MetaData], gongan: Gongan, score: Score) -> None:
    """Processes the metadata of a gongan into the object model.

    Args:
        metadata (list[MetaData]): The metadata to process.
        gongan (Gongan): The gongan to which the metadata applies.
        score (score): The score
    """

    def process_goto(gongan: Gongan, goto: MetaData) -> None:
        for rep in goto.data.passes or [p + 1 for p in range(10)]:
            # Assuming 10 is larger than the max. number of passes.
            gongan.beats[goto.data.beat_seq].goto[rep] = score.flowinfo.labels[goto.data.label]

    haslabel = False  # Will be set to true if the gongan has a metadata Label tag.
    for meta in sorted(metadata, key=lambda x: x.data._processingorder_):
        match meta.data:
            case TempoMeta():
                if meta.data.beat_count == 0:
                    # immediate tempo change.
                    gongan.beats[meta.data.first_beat_seq].tempo_changes.update(
                        {
                            pass_: Beat.TempoChange(new_tempo=meta.data.bpm, incremental=False)
                            for pass_ in meta.data.passes
                        }
                    )
                else:
                    # Stepwise tempo change over meta.data.beats beats. The first tempo change is after first beat.
                    # This emulates a gradual tempo change.
                    beat = gongan.beats[meta.data.first_beat_seq]
                    steps = meta.data.beat_count
                    for _ in range(meta.data.beat_count):
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

            case LabelMeta():
                # Add the label to flowinfo
                haslabel = True
                score.flowinfo.labels[meta.data.name] = gongan.beats[meta.data.beat_seq]
                # Process any GoTo pointing to this label
                goto: MetaData
                for sys, goto in score.flowinfo.gotos[meta.data.name]:
                    process_goto(sys, goto)
            case GoToMeta():
                # Add goto info to the beat
                if score.flowinfo.labels.get(meta.data.label, None):
                    process_goto(gongan, meta)
                else:
                    # Label not yet encountered: store GoTo obect in flowinfo
                    score.flowinfo.gotos[meta.data.label].append((gongan, meta))
            case RepeatMeta():
                # Special case of goto: from last back to first beat of the gongan.
                for counter in range(meta.data.count):
                    gongan.beats[-1].goto[counter + 1] = gongan.beats[0]
            case KempliMeta():
                # Suppress kempli.
                # TODO status=ON will never be used because it is the default. So attribute status can be discarded.
                # Unless a future version enables to switch kempli off until a Kempli ON tag is encountered.
                gongan.gongantype = meta.data.status
                if meta.data.status is MetaDataSwitch.OFF:
                    for beat in gongan.beats:
                        if InstrumentPosition.KEMPLI in beat.staves:
                            beat.staves[InstrumentPosition.KEMPLI] = create_rest_stave(Stroke.SILENCE, beat.duration)
            case GonganMeta():
                # TODO: how to safely synchronize all instruments starting from next regular gongan?
                gongan.gongantype = meta.data.type
            case SilenceMeta():
                # Add a separate silence stave to the gongan beats for each instrument position and pass mentioned.
                for beat in gongan.beats:
                    if beat.id in meta.data.beats or not meta.data.beats:
                        for position in meta.data.positions:
                            beat.exceptions.update(
                                {
                                    (position, pass_): create_rest_stave(Stroke.EXTENSION, beat.duration)
                                    for pass_ in meta.data.passes
                                }
                            )
            case ValidationMeta():
                for beat in [b for b in gongan.beats if b.id in meta.data.beats] or gongan.beats:
                    beat.validation_ignore.extend(meta.data.ignore)

                pass
            case _:
                raise ValueError(f"Metadata value {meta.data.metatype} is not supported.")

    if haslabel:
        # Gongan has one or more Label metadata items: explicitly set the current tempo for each beat by copying it
        # from its predecessor. This will ensure that a goto to any of these beats will pick up the correct tempo.
        for beat in gongan.beats:
            if not beat.tempo_changes and beat.prev:
                beat.tempo_changes.update(beat.prev.tempo_changes)
        return


def passes_str_to_tuple(rangestr: str) -> list[int]:
    """Converts a pass indicator following a position tag to a list of passes.
        A colon (:) separates the position tag and the pass indicator.
        The indicator has one of the following formats:
        <pass>[,<pass>...]
        <firstpass>-<lastpass>
        where <pass>, <firstpass> and <lastpass> are single digits.
        e.g.:
        gangsa p:2,3

    Args:
        rangestr (str): the pass range indicator, in the prescribed format.

    Raises:
        ValueError: string does not have the expected format.

    Returns:
        list[int]: a list of passes (passes are numbered from 1)
    """
    if not re.match(r"^(\d-\d|(\d,)*\d)$", rangestr):
        raise ValueError(f"Invalid value for passes: {rangestr}")
    if re.match(r"^\d-\d$", rangestr):
        return list(range(int(rangestr[0]), int(rangestr[2]) + 1))
    else:
        return tuple(json.loads(f"[{rangestr}]"))


def create_score_object_model(run_settings: RunSettings) -> Score:
    """Creates an object model of the notation. The method aggregates each note and the corresponding diacritics
       into a single note object, which will simplify the generation of the MIDI file content.

    Args:
        datapath (str): path to the data folder
        infilename (str): name of the csv input file
        title (str): Title for the notation

    Returns:
        Score: Object model containing the notation information.
    """
    # Create enough column titles to accommodate all the notation columns, then read the notation
    columns = ["orig_tag"] + ["BEAT" + str(i) for i in range(1, 33)]
    df = pd.read_csv(run_settings.notation.filepath, sep="\t", names=columns, skip_blank_lines=False, encoding="UTF-8")
    df["id"] = df.index
    # Remove empty rows at the start of the document and multiple empty rows between gongans.
    # Gongans should be separated by exactly one empty row.
    df.loc[0, "delete"] = True if type(df.loc[0, "orig_tag"]) == float else False
    for i in range(1, len(df)):
        df.loc[i, "delete"] = type(df.loc[i, "orig_tag"]) == float and type(df.loc[i - 1, "orig_tag"]) == float
    df = df[df["delete"] == False].reset_index()
    # Create a column with the optional pass indicator (indicated by a colon (:) immediately following a position tag).
    # Add a default pass value -1 if pass indicator is missing.
    df["passes"] = df["orig_tag"].apply(
        lambda x: None if not isinstance(x, str) else passes_str_to_tuple(x.split(":")[1]) if ":" in x else (DEFAULT,)
    )
    # Remove optional pass indicator from orig_tag
    df["orig_tag"] = df["orig_tag"].apply(lambda x: x.split(":")[0] if isinstance(x, str) and ":" in x else x)
    # insert a column with the normalized instrument/position names and duplicate rows that contain multiple positions
    df.insert(1, "tag", df["orig_tag"].apply(lambda val: TAG_TO_POSITION_LOOKUP.get(val, [])))
    df = df.explode("tag", ignore_index=True)
    # Copy other tags (meta and comment) from orig_tag
    df["tag"] = np.where(df["tag"].isnull(), df["orig_tag"], df["tag"])
    df.drop("orig_tag", axis="columns", inplace=True)
    # Drop all empty columns
    df.dropna(how="all", axis=1, inplace=True)
    # Number the gongans: blank lines denote start of new gongan. Then delete blank lines.
    df["sysnr"] = df["tag"].isna().cumsum()[~df["tag"].isna()] + 1
    # Reshape dataframe so that there is one beat per row. Column "BEAT" will contain the beat content.
    df = pd.wide_to_long(df, ["BEAT"], i=["sysnr", "tag", "passes", "id"], j="beat_nr").reset_index(inplace=False)
    df = df[~df["BEAT"].isna()]
    df["sysnr"] = df["sysnr"].astype("int16")

    # convert to list of gongans, each gongan containing optional metadata and a list of instrument parts.
    df_dict = df.groupby(["sysnr", "beat_nr", "tag", "passes"])["BEAT"].apply(lambda g: g.values.tolist()).to_dict()
    # Create notation dict that is grouped by gongan and beat
    notation = defaultdict(lambda: defaultdict(lambda: defaultdict(lambda: defaultdict(list))))
    for (sysnr, beat_nr, tag, passes), beat in df_dict.items():
        if tag in InstrumentPosition:
            # Notation contains optional pass information (default (-1,) was added above for gongans without pass info)
            position = tag  # for code clarity
            for pass_ in passes:
                # In case of notation, beat contains exactly one element: a string of notation characters for the position.
                notation[sysnr][beat_nr][position][pass_] = beat[0]
        else:
            # other tags (metadata, comment). Beat can contain multiple values for each tag.
            notation[sysnr][beat_nr][tag] = beat

    # create a list of all instrument positions
    positions_str = set(df[~df["tag"].isin(NON_INSTRUMENT_TAGS)]["tag"].unique())
    all_positions = sorted([InstrumentPosition[pos] for pos in positions_str], key=lambda p: p.sequence)

    score = Score(
        settings=run_settings,
        instrument_positions=set(all_positions),
        balimusic_font_dict=SYMBOL_TO_NOTE_LOOKUP,
        midi_notes_dict=SYMBOLVALUE_TO_MIDINOTE_LOOKUP,
        position_range_lookup=POSITION_TO_RANGE_LOOKUP,
    )
    beats: list[Beat] = []
    metadata: list[MetaData] = []
    comments: list[str] = []
    for sys_id, sys_info in notation.items():
        for beat_nr, beat_info in sys_info.items():
            # create the staves (regular and exceptions)
            # TODO merge Beat.staves and Beat.exceptions and use pass=-1 for default stave. Similar to Beat.tempo_changes.
            try:
                staves = {
                    position: [SYMBOL_TO_NOTE_LOOKUP[symbol].model_copy() for symbol in notationchars[DEFAULT]]
                    for position, notationchars in beat_info.items()
                    if position in InstrumentPosition
                }
                exceptions = {
                    (position, pass_): [SYMBOL_TO_NOTE_LOOKUP[symbol].model_copy() for symbol in notationchars[pass_]]
                    for position, notationchars in beat_info.items()
                    if position in InstrumentPosition
                    for pass_ in notationchars.keys()
                    if pass_ > 0
                }
            except Exception as e:
                raise ValueError(f"unexpected character in beat {sys_id}-{beat_nr}: {e}")

            # Create the beat and add it to the list of beats
            new_beat = Beat(
                id=beat_nr,
                sys_id=sys_id,
                staves=staves,
                exceptions=exceptions,
                bpm_start={DEFAULT: (bpm := score.gongans[-1].beats[-1].bpm_end[-1] if score.gongans else 0)},
                bpm_end={DEFAULT: bpm},
                duration=max(
                    sum(note.total_duration for note in notes if note.pitch != Pitch.NONE)
                    for notes in list(staves.values())
                ),
            )
            prev_beat = beats[-1] if beats else score.gongans[-1].beats[-1] if score.gongans else None
            # Update the `next` pointer of the previous beat.
            if prev_beat:
                prev_beat.next = new_beat
                new_beat.prev = prev_beat
            beats.append(new_beat)

            # Add metadata tags to the beat
            for meta in beat_info.get(METADATA, []):
                # Note that `meta`` is not a valid json string.
                # It will be converted to the required json format by the MetaData class.
                metadata.append(MetaData(data=meta))

            # Add comment tags to the beat
            for comment in beat_info.get(COMMENT, []):
                comments.append(comment)

        # Create a new gongan
        if beats:
            gongan = Gongan(
                id=int(sys_id), beats=beats, beat_duration=beats[0].duration, metadata=metadata, comments=comments
            )
            score.gongans.append(gongan)
            metadata = []
            beats = []
            comments = []

    # Apply font-specific modifications
    postprocess(score)
    for gongan in score.gongans:
        apply_metadata(gongan.metadata, gongan, score)
    # Add kempli beats and blank staves for all other omitted instruments
    add_missing_staves(score)

    return score


def add_attenuation_time(tracks: list[MidiTrackX], seconds: int) -> None:
    """Extends the duration of the final note in each channel to avoid an abrupt ending of the audio.

    Args:
        tracks (list[MidiTrackX]): Tracks for which to extend the last note.
        seconds (int): Duration of the extension.
    """
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
    outfilepathfmt = score.settings.notation.midi_out_filepath
    mid = MidiFile(ticks_per_beat=96, type=1)

    for position in sorted(score.instrument_positions, key=lambda x: x.sequence):
        track = notation_to_track(score, position)
        mid.tracks.append(track)
    add_attenuation_time(mid.tracks, seconds=ATTENUATION_SECONDS_AFTER_MUSIC_END)
    outfilepath = outfilepathfmt.format(position="", midiversion=score.settings.midi.midiversion, ext="mid")
    mid.save(outfilepath)
    print(f"File saved as {outfilepath}")


def convert_notation_to_midi():
    """This method does all the work.
    All settings are read from the (YAML) settings files.
    """
    run_settings = get_run_settings()
    read_settings(run_settings)
    if run_settings.options.validate_settings:
        validate_settings(run_settings)

    score = create_score_object_model(run_settings)
    validate_score(score=score, settings=run_settings)

    if run_settings.options.create_midifile:
        create_midifile(score)


if __name__ == "__main__":
    convert_notation_to_midi()
