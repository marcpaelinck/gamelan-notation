import pandas as pd

from notation_classes import Character, MidiNote

if __name__ == "__main__":
    midinotes_obj = pd.read_csv("./settings/midinotes.csv", sep="\t").to_dict(orient="records")
    midinotes = [MidiNote.model_validate(note) for note in midinotes_obj]
    balifont_obj = pd.read_csv("./settings/balimusic4font.csv", sep="\t").to_dict(orient="records")
    balifont = [Character.model_validate(character) for character in balifont_obj]
    x = 1
