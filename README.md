# Gamelan Notation
This application creates MIDI files from the notation of Balinese gamelan.

## Installation
This project uses pyenv-win and pyenv-win-venv for Windows
See https://pyenv-win.github.io/pyenv-win/ and https://github.com/pyenv-win/pyenv-win-venv

To install a python version (if not available yet):
```
    venv install <python version>
```

To create and activate an environment:

```
pyenv-venv install <python version> <environment name>
pyenv-venv activate <environment name>
```
Install Poetry, see https://python-poetry.org/docs/. Then install dependencies with the command:
```
poetry install
```

## Notation file conventions
### Encoding
Be sure to save the tsv files as UTF-8 encoded (many text editors such as TextPad let the user select this option when saving a file). Other formats might give problems parsing some specific UTF-coded characters.

### General syntax
- Each row should either be empty (except for tab characters) or have the following structure:
  ```
    <tag>\t<content>
  ```
  where \t stands for a tab character.
- `<tag>` can have the following values:
    - The name of an instrument position (see below) - indicates that `<content>` contains notation for the given position.
    - `comment` - the `<content>` part of the line will be ignored.
    - `metadata` - indicates that `<content>` contains information about tempo, sequence of execution (labels and `GOTO` statements), dynamics, etc. See below for a more detailed explanation.

Here is an example of the beginning of the Baris notation (omitting several instruments for simplicity):


![balifont_notation_example.png](balifont_notation_example.png)

## Bali Music TTF font
The above notation is displayed using the BaliMusic5 TrueType font. This font was created for the notation of Balinese (gong kebyar) music. With a regular monospaced font the same content would look like this:


```
comment     BARIS EXAMPLE
metadata    {KEMPLI status=off}                                
metadata    {TEMPO bpm=160}                                
ugal        ...a,    ----     ---i     --oe     ---o     ---e     e/...    ....    ...a,
gangsa4     ...a,    ----     ----     ----     ----     ...e     e/...    ....    ...a,
reyong1+3   ...b     ----     ----     ----     ----     ...b     b/...    ....    ...a,
reyong2+4   ...b     ----     ----     ----     ----     ...b     b/...    ....    ...e
calung      ....     ....     ....     ....     ....     ....     ....     ....    ...a
jegogan     ....     ....     ....     ....     ....     ....     ....     ....    ...a
gong        ....     ....     ....     ....     ....     ....     ....     ....    ...G
    
ugal        ---o     ---i     --oe     ---o     ---e     --oi     -o-e     -u-a
gangsa4     -a,-o    -o-i     -i-e     -e-o     -o-e     -e-i     -o-e     -u-a
reyong1+3   .a,i.    a,ia,.   ia,.i    .a,i.    a,.ia,   .i.a,    i.a,.    oe..
reyong2+4   .e.o     e.eo     .eo.     oe.o     eo.e     o.oe     .oe.     ..ua
calung      ----     ---i     ----     ---o     ----     ---i     ----     ---a
jegogan     ----     ----     ----     ---o     ----     ----     ----     ---a
gong        ----     ----     ----     ---G     ---P     ----     ---P     ---G

```
Metadata or comment lines can either appear at the top or at the bottom of a gongan. The position will not affect the functionality of a metadata tag. Gongan should be separated by one or more empty line(s).

Terminology:
- **tag** - the text at the beginning of a line (*comment*, *metadata* or the name of an instrument or instrument position).
- **beat** - group of notes corresponding with one kempli beat. Each beat should be separated by a tab character. The kempli beats will be added by default and do not need to be written in the notation. For technical reasons, the kempli beat is added at the beginning of a beat. As a consequence the GIR should occur at the beginning of the first beat.
- **flow** - the sequence in which the beats should be played. By default, the flow runs through the gongans in sequence. The flow can be modified with the use of LABEL and GOTO metadata items. These items can be used to repeat parts of the score or to skip to a next part.
- **pass** - value that is incremented each time a beat is played. The first pass is numbered 1. Be aware that if a gongan is repeated but the first beat is skipped the first time, the pass value of this beat will be one lower than that of the other beats in the gongan.
- **octave** - An octave runs from DING through DANG (or DAING for a seven-note tuning). Octaves are numbered from 0 through 2 and are relative to the instrument's range. The numbering depends on the number of octaves that are (partly) covered by the instrument.
  - one octave: value = 1
  - two octaves: the lower octave is numbered 0, the second one 1.
  - three octaves: the octaves are numbered 0 through 3. Usually octaves 0 and 2 will contain fewer notes than octave 1.
  - **metadata** - instructions to the MIDI generator, such as tempo changes, loops and repeats.

### Metadata syntax

General syntax:
```
{<KEYWORD> <parameter>=<value> [, <parameter>=<value> [, ...]]}

example:
{GOTO label=C, passes=[1,2,3]}
```

In the following table, parameters without default value must always be given.

Terminology:
- **list** - comma separated values, enclosed between square brackets, e.g. [1,2,3] or [gangsa polos, gangsa sangsih, ugal].
- **numbering** - the numbering of gongans, beats and passes starts at 1.


| keyword | parameters | values | example |default |comment |
|---------|------------|--------|---------|--------|-------|
| GONGAN  ||||| The type of gongan. this affects whether there will be a kempli beat and whether the beat length will be validated.|
|         | type       | *regular*, *kebyar*, *gineman*     | regular | regular | regular adds a kempli beat and activates validation of the beat length. Gineman and kebyar suppress the kempli and disable beat length validation. |
| DYNAMICS||||| Sets dynamics or a gradual increase/decrease in dynamic. |
|         | positions  | list of position tags   |[gangsa p, gangsa s]  |         | The tags should occur in the tag list below |
|         | value      | p, mp, mf or f                     | mf      |           | The value is translated to a MIDI velocity value: p=60, mp=80, mf=100, f=127. |
|         | first_beat | integer value                      | 3       | 1         | The beat of the gongan where the new dynamics should be applied or where the gradual dynamics change should start |
|         | beat_count | integer value                      | 6       | 0         | If 0, the dynamics are effective from the given beat. If greater than 0, the dynamics will gradually increase/decrease over the number of beats, starting with first_beat |
|         | passes     | list of integer values             |[1]      | all passes| The passes for which the dynamics change applies. |
| GOTO    ||||| Indicates the next beat in the flow sequence. A GOTO can refer either backward or forward in the notation. The GOTO metadata line can appear at the end of a gongan for more clarity. |
|         | label      | Existing LABEL *name* parameter.   | PENGECET|         |  |
|         | from_beat  | int                                | 4       | last    | The beat after which to go to the labelled beat. Beats are numbered from 1. Default is the last beat of the gongan. |
|         | passes     | list of integer values             | [1,2,3] | all     | Passes for which the GOTO will be active. If no passes are given, the GOTO will always be active |
| KEMPLI  ||||| Suppresses the kempli in a *regular* gongan. |
|         | status     |*on* or *off*                       |*off*    |           | Usually *off* will be selected. *on* would only have effect in a *gineman* or *kebyar* gongan. |
|         | beats      | list of integer values             |[5, 6]   | all beats | The beats for which the kempli should be silenced. |
|         | scope      | *GONGAN* or* SCORE*                | GONGAN  | GONGAN    | The scope for which to suppress the validation. |
| LABEL   ||||| Labels a beat in a gongan. Used in combination with GOTO to change the flow sequence. By default the label refers to the first beat of the gongan. |
|         | name       | character string without spaces    | PENGECET|         | 
|         | beat_nr    | integer                            | 2       | 1       | The beat in the gongan to which the label refers. 1 = first beat. |  

| keyword | parameters | values | example |default |comment |
|---------|------------|--------|---------|--------|-------|
| OCTAVATE||||| Indicates that the notation for an instrument should be transposed by one or more octaves |
|         | instrument | label of an instrument             | trompong|         | Can be any tag value in the tag list (see below) |
|         | octaves    | positive or negative int           | -1      |         | Be sure that the resulting note values will all remain within the instrument's range |
|         | scope      | *GONGAN* or* SCORE*                | SCORE   | GONGAN  | The scope for which to octavate: either the current gongan or the entire score. |
| PART    ||||| Indicates the start of a new part of the composition. This action will add a tick mark on the progress bar in the MIDI app.  |
|         | name       | name (may contain space chars)     | PENGAWAK|         |  |
| REPEAT  ||||| Repeats a single gongan. The REPEAT remains effective for each GOTO that redirects to the gongan.   |
|         | count      | integer value                      | 3       |         | Number of times to play the gongan. |
| SUPPRESS||||| Add a period of silence after a gongan. Instruments will not be muted (sound will attenuate). |
|         | seconds    | value with decimals                |2.25     |         | Number of seconds. Will be rounded off to the nearest quarter of a second. |
|         | after      | *true* or *false*                  | false   | true    | Indicates whether the silence should be added before or after the gongan (not operational yet). |

| keyword | parameters | values | example |default |comment |
|---------|------------|--------|---------|--------|-------|
| SUPPRESS||||| used to suppress specific instruments, e.g. during the first pass of a gongan. |
|         | positions  | list of position tags |[gangsa p, gangsa s]  |         | The tags should occur in the tag list below |
|         | passes     | list of integer values             |[1]      | all passes | The passes for which this meta item should be applied. |
|         | beats      | list of integer values             |[5, 6]   | all beats | The beats that should be silenced. |
| TEMPO   ||||| used to set a tempo or a gradual increase/decrease in tempo. |
|         | value      | integer value                      | 120     |           | Beats per minute for 4 full-length notes. |
|         | first_beat | integer value                      | 3       | 1         | The beat of the gongan where the new tempo should be applied or where the gradual tempo change should start |
|         | beat_count | integer value                      | 6       | 0         | If 0, the tempo is effective from the given beat. If greater than 0, the tempo will gradually increase/decrease over the number of beats, starting with first_beat |
|         | passes     | list of integer values             |[1]      | all passes| The passes for which the tempo change applies. |
| VALIDATION ||||| Suppresses specific aspects of the validation and autocorrection. |
|         | beats      | list of integer values             |[5, 6]   | all beats | The beats to which the action applies. |
|         | scope      | *GONGAN* or* SCORE*                | GONGAN   | GONGAN  | The scope for which to suppress the validation. |
|         | ignore     | list of items                      |[kempyung]|       | List of validations that should be skipped. Possible values: *beat-duration*, *stave-length*, *instrument-range*, *kempyung*|


## Vocabulary
### Balinese Music
- `Muted`: key instruments: the key is muted with the left hand while striking it. Reyong: only used for `jet`.
- `Abbreviated`: key instruments: the key is muted shortly after being stricken. Reyong: only used for `byot`.
- `byot`: strike the gongs and then immediately mute them.
- `jet`: strike the gongs without lifting the panggul.

### MIDI files


### MIDI Soundfont files
- `SoundFont`: file which contains audio samples. The samples are organized in a hierachy: `bank` -> `preset` -> `zone` -> `split`
- `bank`: top level of the soundfont hierarchy. Banks are numbered 0..127.
- `preset`: second level of the soundfont hierarchy. Presets are numbered 0..127. Synonymns for preset are `instrument`, `patch` and `program`. A preset defines a unique mapping between audio samples and MIDI notes. A preset can be mapped to a MIDI channel which in turn can be mapped to a MIDI device such as a keyboard.
- `zone`: corresponds with a subset of the MIDI notes of a preset. There is always one zone called `Global`. Zones can be used to further split up the note range into logical groups, for instance in case a preset contains more than one instrument. Concretely this would mean that diffent ranges of a MIDI keyboard that is mapped to the preset would correspond with different instruments. Synonymns for zone are `layer` and `instrument` (note that a preset is sometimes also called an instrument).
- `split`: lowest level of the soundfont hierarchy. A split corresponds with a single audio sample which is mapped to a single MIDI note or to a range of MIDI notes. In the latter case, the `root key` of the split indicates the MIDI note that corresponds with the pitch of the audio sample. The other MIDI notes in the split correspond with a modulation of the audio sample. This modulation is performed by the synthesizer that is connected to the MIDI device (e.g. keyboard). The soundfont includes tuning generators (see below) to specify the required pitch modification.

Zones and splits can contain parameters (usually called `generators`) that can alter the sound of the audio samples. E.g. Velocity Range, Attenuation, Tuning, Volume envelopes for attack, sustain and decay. The zone parameters act as multiplicators for the corresponding split parameters. Presets can share zones and can each have a separate set of generator values for the same zone (instrument). So the same instrument may sound differently depending on which preset is selected.


# Versions
## version 1.3
- New notation parser based on Parser Expression Grammar (PEG). Uses Tatsu library (https://tatsu.readthedocs.io/en/stable/).
- Simplified metadata syntax.
  - tag `metadata` can be omitted.
  - first/main attribute can be given as positional argument, e.g. {TEMPO 80}.
  - arguments can be space-separated (comma no longer compulsory)
- Simplified example syntax: a `#` sign can be used instead of the `comment` tag to define a comment.
- Introduced `Measure` object, which takes the place of the `stave` concept. `stave` is now used for an entire notation line (notes for one position over the entire gongan). In other words: a measure is the intersection of a stave and a beat.