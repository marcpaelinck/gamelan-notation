# pylint: disable=all
import os
import re
import time

from mido import MidiFile


def to_text(path, midifilename):
    midifilepath = os.path.join(path, midifilename)
    txtfilepath = os.path.splitext(midifilepath)[0] + ".txt"

    mid = MidiFile(midifilepath)
    beat = "00-0"
    position = "X"
    with open(txtfilepath, "w", encoding="utf-8") as csvfile:
        for i, track in enumerate(mid.tracks):
            clocktime = 0
            csvfile.write("Track {}: {}".format(i, track.name) + "\n")
            for msg in track:
                do_write = True
                match = re.findall(r"'marker', text='b_(\d+-\d+)'", str(msg))
                if match:
                    beat = match[0]
                    do_write = False
                else:
                    match = re.findall(r"'track_name', name='(\w+)'", str(msg))
                    if match:
                        position = match[0]
                        do_write = False
                clocktime += msg.time
                if do_write:
                    csvfile.write(f"    ({clocktime},{beat},{position}) -- {str(msg)} abstime={clocktime}" + "\n")


def to_text_multiple_files(files: list[str], folders: list[str]):
    for file in files:
        for folder in folders:
            to_text(folder, file)


if __name__ == "__main__":
    to_text("./data/midiplayer", "Legong Mahawidya GK_full_GAMELAN1.mid")
