import os

from mido import MidiFile

# midifile_name = r"C:\Users\marcp\Documents\administratie\_VRIJETIJD_REIZEN\Scripts-Programmas\PythonProjects\gamelan-notation\data\notation\lengker\Lengker_GAMELAN1.mid"
midifile_name = "./data/notation/pendet/Pendet_full_GAMELAN1.mid"
mid = MidiFile(midifile_name)
txt = os.path.splitext(midifile_name)[0] + ".txt"

lines = []
with open(txt, "w") as csvfile:
    for i, track in enumerate(mid.tracks):
        clocktime = 0
        csvfile.write("Track {}: {}".format(i, track.name) + "\n")
        for msg in track:
            clocktime += msg.time
            csvfile.write("    {} -- {}".format(str(msg), clocktime) + "\n")
