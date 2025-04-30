import time

from fluidsynth import Synth

from src.settings.settings import Settings

settings = Settings.get("cendrawasih", "full")

midi_filename = settings.midi_out_filepath
SOUNDFONT_FILE_PATH = "~/Documents/SynthFont/GAMELAN1.sf2"

fs = Synth(samplerate=44100.0)
fs.start(driver="coreaudio")
gongkebyar_sf = fs.sfload(SOUNDFONT_FILE_PATH)
fs.program_select(0, gongkebyar_sf, 0, 0)

fs.play_midi_file(midi_filename)
time.sleep(60)

fs.delete()
