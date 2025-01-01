## Modules in the `notation2midi` Folder

The `notation2midi` folder contains several modules that work together to convert musical notation into MIDI files. Below is a brief explanation of each module:

1. **notation5_to_dict.py**: This module is responsible for parsing the input notation files. It reads and validates the notation data and converts it into a record format that can be processed by other modules. This module processes notation written with the *Bali Music 5* font. To convert other notation types, this is the only module that needs to be rewritten.

2. **dict_to_score.py**: This module takes the parsed notation data and converts it into an object model that has a Score object as root. It processes the metadata into the object model and generates a structure that reflects the notation flow (repeat and goto metadata statements).

3. **score_validation.py**: This module performs a logic validation of the object model. It checks that all beats and gongans have consistent durations an also warns for invalid kempyung values. It optionally corrects errors if possible. A check that the notation only contains valid notes for the respective instruments is not performed here, but implicitly implemented when creating the run settings. See the README doc in that folder for an explanation of the  `font_to_valid_notes` module.

4. **score_to_midi.py**: This module used the object model to write the MIDI events for each instrument to a separate track of a MIDI file. It assigns each track to a separate channel according to the `preset` settings data. The midi_track module is used for the actual generation of MIDI messages.

5. **score_to_notation.py**: This module converts the object model back to a validated and optionally corrected notation file that can be reused as input for this MIDI generator.
