# Data

All tabular data should be tab delimited.


## Font
A Truetype font `Bali Music` is available to facilitate the notation of Balinese (gong kebyar) music. This font maps symbols that are specific for the notation of Balinese music to 'regular' letters and symbols. More specifically, it maps the symbols to unicode values. The font definition file defines this mapping.

The font has been redesigned several times. The `font` subfolder contains definition files for the last two versions (versions 4 and 5). The main difference between these two versions is that v4 uses a separate unicode for each music notation symbol whereas v5 contains `combining` characters that work like diacritics. This results in a much smaller number of characters (131 in v4 and 37 in v5) and simplies the use of the font. For instance the character `ạ` (dang in the lower octave) is written by typing `z` in version 4 and by typing `a,` in version 5: the `,` key adds a lowered dot under the previous character. (`,` is used instead of `.`, because the character `.` indicates a 'rest'). Similarly, `ẹ`, `ọ` and `ụ` are typed as `d`, `l` and `j` in version 4 and as `e,`, `o,` and `u,` in version 5.

The fonts can be downloaded from https://fontstruct.com/fontstructors/499795/marc_paelinck

The font definition files contains the following columns:

| **Font file** |  |
| ------ | --------- |
| `symbol` | Character defined by the unicode value. This is the character that would be displayed using a 'regular' font such as Courier |
| `unicode` | Unicode value (hex representation formatted as `0x0000`). |
| `symbol_description` | Description of the standard unicode symbol. |
| `balifont_symbol_description` | Description of the Bali Font symbol. |
| `pitch`\* | The name of the note or sound such as `DING`, `DONG` (for melodic instruments) or `KEP`, `PAK` (kendang). |
| `octave` | For melodic instruments only: the octave **relative to the instrument's range**. 1 = central octave, 0 = lower octave, 2 = higher octave. An unmodified note (i.e. not followed by a `modifier` or `combining` character) has an `octave` value of 1. |
| `stroke`\* | Indicates the type of stroke, e.g. `OPEN` or `MUTED`. |
| `duration` | Duration of the audible part of the note, relative to the duration of an unmodified note (i.e. not followed by a `modifier` or `combining` character). |
| `rest_after` | Duration of the 'silent part' of the note following the audible part. E.g. in case of a muted note, the `duration` atrribute might be 0.25 and the `rest_after` attribute 0.75, and in the case of a quarter note (indicate with a double dash or _macron_ above the character), the `duration` attribute would be 0.25 and the `rest_after` attribute would be 0 |
| `modifier`\* | Indicates that the symbol does not represent a note value but is a `modifier` for the preceding note(s). In v5 of the Bali Music font, this applies to all _combining_ characters. The value of this attribute indicates the type of modification (e.g. octavated or muted). |
| `description` | description of the note value or modification that corresponds with the symbol. |

\* See corresponding `Enum` classes in `src/constants/metadata_classes.py` for possible values.


## instruments

Instrument description consists of two files. 
- **Instruments file**: a list of all instruments in the orchestra (orchestra is the same as instrument group).
- **Tag file**: a list of tags or labels used in the notation file to denote the instruments with the corresponding instrument positions as listed in the Instruments file. This allows to process existing notation files without the need to rename the instrument tags.

The term *position* denotes either the physical position on a single instrument that is played by more than one player (reyong), or one of multiple parts played on the same instrument type (polos, sangsih)

| **Instruments file** |  |
| ------ | --------- |
| `group`\* | Orchestra type, e.g. GONG_KEBYAR, SEMAR_PAGULINGAN. |
| `position`\* | The position as described above. e.g. PEMADE_POLOS, REYONG_1. Each row should contain exactly one position. |
| `instrument`\* | Name of the instrument, e.g. GANGSA, KENDANG. |

| **Tag file** |  |
| ------ | --------- |
| `tag` | The exact string as it occurs in the notation file(s). |
| `infile` | (optional) the list of notation files in which the tag is used. |
| `positions`\* | List of positions denoted by the tag, as a JSON-type list. E.g. [KANTILAN_POLOS, KANTILAN_SANGSIH]. |

\* See corresponding `Enum` classes in `src/constants/metadata_classes.py` for possible values.

It is OK to include multiple tags for the same position(s). Each tag should occur in a separate row.


## midi

Sets the relation between the MIDI definitions and the instruments.
The data consists of two files.
- **Midinotes file**: Maps each midi note to the corresponding note of an instrument in the orchestra.
- **Presets file**: Description of MIDI presets. This file is only needed when creating a soundfont definition file and can otherwise be omitted.

| **Midinotes file** |  |
| ------ | --------- |
|`instrumentgroup`\* | Orchestra type, e.g. GONG_KEBYAR, SEMAR_PAGULINGAN. |
| `instrumenttype`\* | Name of the instrument. |
| `positions`\* | To be used if the note can not be played by all positions of the instrument, e.g. in case of a reyong. Should otherwise be left empty. |
| `pitch`\* | The name of the note or sound |
| `octave`\* | The octave relative to the instrument's range. |
| `stroke`\* | The stthe type of stroke. |
| `remark` | (optional) |
| `midinote` | Integer MIDI note value  |
| `sample`| Name of the (.mp3) audio file containing the sound for the note. |

| **Presets file** |  |
| ------ | --------- |
|`instrumentgroup`\* | Orchestra type, e.g. GONG_KEBYAR, SEMAR_PAGULINGAN. |
| `instrumenttype`\* | Name of the instrument. |
| `bank` | MIDI bank number (0-127). |
| `preset` | MIDI preset value (0-127). |
| `preset_name`\* | Name with which to denote the preset. |

\* See corresponding `Enum` classes in `src/constants/metadata_classes.py` for possible values.


## notation

The folder contains the notation files and is also used to save the MIDI conversion of the notation files. Notation files can be stored in separate subfolders. See subfolder `test` for an example.

## samples

This folder contains the audio sample files listed in the Midinotes file.

## soundfont

This is an output folder for the soundfont file generator.

## content.json
This file contains information for the online midi player. It should be updated each time a new MIDI file has been created (set update_content_json_file run setting to `true`)