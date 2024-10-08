# Data
## Font
A Truetype font `Bali Music` is available to facilitate the notation of Balinese (gong kebyar) music. This font maps regular letters and symbols to symbols that are specific for the notation of Balinese music. More specifically, it maps these symbols to unicode values. The font definition file define this mapping.


The font has been redesigned several times. The `font` subfolder contains definition files for the last two versions (versions 4 and 5). The main difference between these two versions is that v4 uses a separate unicode value to represent each symbol whereas v5 contains `combining` characters that act somewhat as diacritics. This results in a much smaller number of characters (131 in v4 and 37 in v5), which simplies the use of the font. For instance the character `ạ` (dang in the lower octave) is written by typing `z` in version 4 and by typing `a,` in version 5: the `,` key maps to a lowered dot that is displayed under the previous character. (`,` is used instead of `.`, because the `.` key is used for the `.` character that indicates a 'rest'). Similarly, `ẹ`, `ọ` and `ụ` are typed as `d`, `l` and `j` in version 4 and as `e,`, `o,` and `u,` in version 5.

The fonts can be downloaded from https://fontstruct.com/fontstructors/499795/marc_paelinck