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
