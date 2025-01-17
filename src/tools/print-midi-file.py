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


if __name__ == "__main__":
    dir_old = "./data/notation/_parserold"
    dir_new = "./data/notation/_parsernew"
    files = [
        # "Bapang Selisir_entire piece_GAMELAN1.mid",
        # "Cendrawasih_entire piece_GAMELAN1.mid",
        # "Gilak Deng_entire piece_GAMELAN1.mid",
        # "Godek Miring_entire piece_GAMELAN1.mid",
        # "Legong Mahawidya_entire piece_GAMELAN1.mid",
        # "Lengker_entire piece_GAMELAN1.mid",
        # "Margapati_entire piece_GAMELAN1.mid",
        # "Pendet_entire piece_GAMELAN1.mid",
        # "Rejang Dewa_entire piece_GAMELAN1.mid",
        "Sekar Gendot_entire piece_GAMELAN1.mid",
        # "Sinom Ladrang (GK)_entire piece_GAMELAN1.mid",
        # "Sinom Ladrang_entire piece_GAMELAN1.mid",
    ]
    for file in files:
        # to_text(dir_old, file)
        to_text(dir_new, file)
