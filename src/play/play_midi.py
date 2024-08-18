import os
import time

from fluidsynth import Synth

from src.settings import CENDRAWASIH, SOUNDFONT_FILE

midi_filename = os.path.join(CENDRAWASIH.datapath, "Cendrawasih _MULTIPLE_INSTR.mid")

fs = Synth(samplerate=44100.0)
fs.start(driver="coreaudio")
gongkebyar_sf = fs.sfload(SOUNDFONT_FILE)
fs.program_select(0, gongkebyar_sf, 0, 0)

fs.play_midi_file(midi_filename)
time.sleep(60)

fs.delete()
