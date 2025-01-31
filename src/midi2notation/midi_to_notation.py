import math
import os
from dataclasses import dataclass
from itertools import batched, pairwise

from mido import MidiFile

from src.common.constants import FROM_PIANO, MIDI_TO_COURIER, VALID_MIDI_MESSAGE_TYPES
from src.common.logger import get_logger
from src.midi2notation.classes import TimedMessage, TimingData

logger = get_logger(__name__)

# datafolder = ".\\data\\puspanjali\\"
datafolder = ".\\data\\cendrawasih\\"

BEATS_PER_GONGAN = 16


SPECIFICS = {
    "Cendrawasih gangsa P.mid": {
        "sections": [
            {"start": 0, "end": None, "gongan": None},
        ],
    },
    "Cendrawasih gangsa P.mid": {
        "sections": [
            {"start": 0, "end": None, "gongan": None},
        ],
    },
    "Puspanjali Intro P.mid": {
        "sections": [
            {"start": 0, "end": 32, "gongan": None},
            {"start": 33, "end": None, "gongan": {"length": 16, "pattern": [("G", 0), ("P", 4), ("T", 8), ("P", 12)]}},
        ],
    },
    "Puspanjali Intro S.mid": {
        "time_correction": {4: 0, 20: 24, 28: 24},
        "sections": [
            {"start": 0, "end": 32, "gongan": None},
            {"start": 33, "end": None, "gongan": {"length": 16, "pattern": [("G", 0), ("P", 4), ("T", 8), ("P", 12)]}},
        ],
    },
    "Puspanjali Mid P.mid": {
        "insert_before": [{"type": "rest", "units": 1}],
        "sections": [
            {"start": 0, "end": 8, "gongan": None},
            {"start": 9, "end": None, "gongan": {"length": 32, "pattern": [("G", 0), ("P", 8), ("T", 16), ("P", 24)]}},
        ],
    },
    "Puspanjali Mid S.mid": {
        "insert_before": [{"type": "rest", "units": 1}],
        "sections": [
            {"start": 0, "end": 8, "gongan": None},
            {"start": 9, "end": None, "gongan": {"length": 32, "pattern": [("G", 0), ("P", 8), ("T", 16), ("P", 24)]}},
        ],
    },
    "Puspanjali End P.mid": {
        "sections": [
            {"start": 0, "end": None, "gongan": {"length": 16, "pattern": [("G", 0), ("P", 4), ("T", 8), ("P", 12)]}}
        ],
    },
    "Puspanjali End S.mid": {
        "sections": [
            {"start": 0, "end": None, "gongan": {"length": 16, "pattern": [("G", 0), ("P", 4), ("T", 8), ("P", 12)]}}
        ],
    },
}


def get_metadata(mid: MidiFile, beats_per_gongan):
    for msg in mid:
        if msg.type == "time_signature":
            unit_duration = int(msg.notated_32nd_notes_per_beat * (math.log2(32 // msg.denominator)))
            metadata = TimingData(
                unit_duration=unit_duration, units_per_beat=msg.numerator, beats_per_gongan=beats_per_gongan
            )
            return metadata
    return None


def apply_specifics(message_list: list[TimedMessage], filename: str, metadata: TimingData):
    """Apply specific changes stored in variable SPECIFICS

    Args:
        obj (list[TimedMessage]): list of messages

    Returns:
        list[TimedMessage]: the modified list
    """
    # Modify individual messages
    # correct overlapping notes
    time_correction = SPECIFICS.get(filename, {}).get("time_correction", {})
    if time_correction:
        for message in message_list:
            new_time = time_correction.get(message.time, message.time)
            message.time = new_time

    # Add messages
    item_list = SPECIFICS.get(filename, {}).get("insert_before", [])
    prepend = []
    for item in item_list:
        prepend.append(TimedMessage(time=item["units"] * metadata.unit_duration, type=item["type"]))
    message_list = prepend + message_list

    return message_list


def get_timed_messages(mid: MidiFile, metadata: TimingData):
    notemessages = [
        TimedMessage(
            msg.time,
            msg.type,
            MIDI_TO_COURIER.get(msg.note, MIDI_TO_COURIER.get(FROM_PIANO.get(msg.note, 0), 0)),
            -1,
        )
        for msg in mid.tracks[0]
        if msg.type in VALID_MIDI_MESSAGE_TYPES
    ]
    filename = os.path.basename(mid.filename)
    notemessages = apply_specifics(notemessages, filename, metadata)

    cumtime = 0
    for msg in notemessages:
        cumtime += msg.time
        msg.cumtime = cumtime

    notemessages = sorted(
        notemessages, key=lambda m: m.cumtime * 10 + (0 if m.type == "rest" else (1 if m.type == "note_off" else 2))
    )

    valid_sequence = True
    for msg1, msg2 in pairwise(notemessages):
        valid_sequence = (
            valid_sequence and msg1.type != msg2.type and (msg2.type == "note_on" or msg2.note == msg1.note)
        )
        if not valid_sequence:
            raise Exception(f"invalid sequence of events: {msg1} {msg2}")
        msg1.duration = msg2.cumtime - msg1.cumtime

    return notemessages


def generate_grouping(mid: MidiFile):
    metadata = get_metadata(mid, beats_per_gongan=BEATS_PER_GONGAN)
    timed_messages = get_timed_messages(mid, metadata)

    notes = []
    notes.extend(["."] * max((timed_messages[0].cumtime // 24), 0))

    for msg in timed_messages:
        if msg.type in ("note_off", "rest"):
            notes.extend(["."] * max((msg.duration // 24), 0))
        if msg.type == "note_on":
            notes.extend([msg.note] + ["-"] * max((msg.duration // 24) - 1, 0))

    # separate in sections according to SPECIFICS
    filename = os.path.basename(mid.filename)
    sections = [
        notes[
            section["start"]
            * metadata.units_per_beat : None if not section["end"] else (section["end"] + 1) * metadata.units_per_beat
        ]
        for section in SPECIFICS.get(filename, {}).get("sections", [{"start": 0, "end": None}])
    ]

    grouping = [
        [[note for note in beat] for beat in batched(gongan, metadata.units_per_beat)]
        for section in sections
        for gongan in batched(section, metadata.units_per_beat * metadata.beats_per_gongan)
    ]

    return grouping


if __name__ == "__main__":
    # mid_polos = MidiFile(datafolder + "Puspanjali Intro P.mid", clip=True)
    # mid_sangsih = MidiFile(datafolder + "Puspanjali Intro S.mid", clip=True)
    mid_polos = MidiFile(datafolder + "Cendrawasih gangsa p.mid", clip=True)
    x = 1
    # mid_sangsih = MidiFile(datafolder + "Cendrawasih_piano.mid", clip=True)
    grouping_polos = generate_grouping(mid_polos)
    # grouping_sangsih = generate_grouping(mid_sangsih)
    p_gongans = ["|".join("".join([note for note in beat]) for beat in gongan) for gongan in grouping_polos]
    s_gongans = ["|".join("".join([note for note in beat]) for beat in gongan) for gongan in grouping_sangsih]

    notation = "\n\n".join("\n".join((p_gongan, s_gongan)) for (p_gongan, s_gongan) in zip(p_gongans, s_gongans))
    logger.info(notation)
