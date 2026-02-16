# Comparison of kendang parts of Midi file (Lester) with JSON export from Laras (LLuís)
#
import json
from dataclasses import dataclass

from mido import Message, MetaMessage, MidiFile

from src.common.constants import Pitch, Position, Stroke

channels = {0: Position.KENDANG}
midiNotes = {
    36: [Pitch.DE, Stroke.DETUT, "9"],
    37: [Pitch.CUNG, Stroke.CUNGKUNG, "0"],
    38: [Pitch.R, Stroke.LR, "R"],
    39: [Pitch.L, Stroke.LR, "L"],
    40: [Pitch.KUNG, Stroke.CUNGKUNG, ")"],
    41: [Pitch.TONG, Stroke.TONGTENG, "o"],
    42: [Pitch.TENG, Stroke.TONGTENG, "e"],
    43: [Pitch.PLAK, Stroke.NONE, "K"],
}
midiNotes = {
    36: [Pitch.DE, Stroke.DETUT, "D"],
    37: [Pitch.CUNG, Stroke.CUNGKUNG, "T"],
    38: [Pitch.R, Stroke.LR, "<"],
    39: [Pitch.L, Stroke.LR, ">"],
    40: [Pitch.KUNG, Stroke.CUNGKUNG, "u"],
    41: [Pitch.TONG, Stroke.TONGTENG, "o"],
    42: [Pitch.TENG, Stroke.TONGTENG, "e"],
    43: [Pitch.PLAK, Stroke.NONE, "K"],
}

BEATS = 8
NOTES = 8
SILENCE = " "


@dataclass
class Note:
    symbol: str
    pitch: Pitch
    stroke: Stroke
    time: int
    duration: str


def toGongan(notation: str):
    whole_measures = int(len(notation) / 8)
    last_measure = 8 * int(len(notation) / 8) != len(notation)
    score = [notation[8 * i : 8 * i + 8] for i in range(whole_measures)] + (
        [notation[whole_measures * 8 : -1]] if last_measure else []
    )
    whole_gongans = int(len(score) / 8)
    last_gongan = 8 * int(len(score) / 8) != len(score)
    score = [score[8 * i : 8 * i + 8] for i in range(whole_gongans)] + (
        [score[whole_gongans * 8 : -1]] if last_gongan else []
    )
    return score


def readMidi(name: str):
    midiFile = MidiFile(name)
    playing = {}
    notes: list[Note] = []
    message: Message | MetaMessage
    curr_time = 0
    for message in midiFile.tracks[0]:
        if message.is_meta:
            continue
        if message.type == "note_on":
            curr_time += message.time / 24
            if playing.get(message.note, None):
                raise ValueError("missing note_off message")
            message.time = curr_time
            playing[message.note] = message
        if message.type == "note_off":
            curr_time += message.time / 24
            if not playing.get(message.note, None):
                raise ValueError("missing note_on message")
            if message.note not in playing:
                raise ValueError(f"Unknown note number {message.note}")
            message.time = curr_time
            note_on = playing[message.note]
            notes.append(
                Note(
                    symbol=midiNotes[message.note][2],
                    pitch=midiNotes[message.note][0],
                    time=note_on.time,
                    stroke=midiNotes[message.note][1],
                    duration=message.time - note_on.time,
                )
            )
            if int(notes[-1].duration) != notes[-1].duration:
                print([notes[-1].duration, len(notes)])
            playing[message.note] = None

    notes.sort(key=lambda note: note.time)
    # Add silence symbols for notes with duration > 1 and transform into a single string
    # Also add an extra beat at the start (midi starts with beat 2 of the pengawak)
    notation = [n1.symbol + SILENCE * int(n2.time - n1.time - 1) for n1, n2 in zip(notes, notes[1:] + [notes[-1]])]
    notation = SILENCE * 8 + "".join(notation)
    return toGongan(notation)


def readJsonLaras(file):
    # Select only pengawak
    jscore: str
    with open(file, "r", encoding="utf-8") as infile:
        jscore = json.load(infile)
    score = [
        data["value"]
        for section in jscore["sections"]
        if "Pengawak" in section["title"]
        for data in section["data"]
        if data["label"] == "kkr"
    ]
    # Return a single string
    return toGongan("".join(score))


def comparePrint(score1, score2):
    for i, (line1, line2) in enumerate(zip(score1, score2)):
        print(f"{i+13}  L :  {" | ".join(line1)}\n    LL:  {" | ".join(line2)}\n")


# contains only pengawak
fileName = "./data/midifiles/Mahawidya Pengawak Kendang 2.mid"
# entire score
fileNameL = "./data/notation/legong mahawidya/Legong Kreasi JSON - Laras.txt"

if __name__ == "__main__":
    scoreL = readMidi(fileName)
    scoreLL = readJsonLaras(fileNameL)
    comparePrint(scoreL, scoreLL)
