#Samples

##Format
In order to create a soundfont, samples need to be in WAV format, and more specifically in PGM format.
These can be created by the *export audio* function in Audacity.

##Root Key and pitch correction
In order to keep the SoundFont file small, the latest version only contains one sample for each instrument.
The unmodified sample should be assigned to a key which is called the Root Key. Viena suggests a root key based on a spectrum analysis of the sample. Viena also calculates a pitch correction which is automatically applied to the sample. As a consequence, the inverse of this correction should be applied tot the root key in the Instruments section of the SoundFont definition file. The other notes should be defined using the same sample and corresponding correction. File Soundfont corrections.xlsx can be used to calculate these corrections. It also contains some more explanation about this processs.

#Notes

## Presets for muted notes (instead of samples)
In the SoundFont preset definition, use the following settings to emulate `abbreviated` and `muted` notes
if there is no separate sample for these values (determined based on GK pemade samples).
For both:
- Vol Env Sustain = 144
- Vol Env Release = 0.05
For `abbreviated`
- Vol Env Decay = 0.5
For `muted`:
- Vol Env Decay = 0.1