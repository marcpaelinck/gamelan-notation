from mido import MidiFile

mid = MidiFile("data/notation/cendrawasih/Cendrawasih _GONG_KEBYAR1_channels.mid")

lines = []
with open("data/notation/cendrawasih/Cendrawasih _GONG_KEBYAR1_channels.txt", "w") as csvfile:
    for i, track in enumerate(mid.tracks):
        clocktime = 0
        csvfile.write("Track {}: {}".format(i, track.name) + "\n")
        for msg in track:
            clocktime += msg.time
            csvfile.write("    {} -- {}".format(str(msg), clocktime) + "\n")
