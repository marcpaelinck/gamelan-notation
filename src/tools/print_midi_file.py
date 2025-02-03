import os

from mido import MidiFile


def to_text(path, midifilename):
    midifilepath = os.path.join(path, midifilename)
    txtfilepath = os.path.splitext(midifilepath)[0] + ".txt"

    lines = []
    mid = MidiFile(midifilepath)
    with open(txtfilepath, "w") as csvfile:
        for i, track in enumerate(mid.tracks):
            clocktime = 0
            csvfile.write("Track {}: {}".format(i, track.name) + "\n")
            for msg in track:
                clocktime += msg.time
                csvfile.write(f"    {str(msg)} -- {clocktime}" + "\n")


def to_text_multiple_files(files: list[str], folders: list[str]):
    for file in files:
        for folder in folders:
            to_text(folder, file)


if __name__ == "__main__":
    to_text("./data/midiplayer/", "Cendrawasih_full_GAMELAN1.mid")
