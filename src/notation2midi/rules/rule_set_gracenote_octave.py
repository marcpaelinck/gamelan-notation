from src.common.classes import Measure
from src.common.constants import Position, Stroke
from src.common.notes import Note, NoteFactory, Tone
from src.notation2midi.metadata_classes import MetaData
from src.notation2midi.patterns.tremolo_pattern import TremoloPatternGenerator
from src.notation2midi.rules.rule import Instrument, Rule


class RuleSetGracenoteOctave(Rule):
    NAME = "Determine octave for grace notes"

    def update_grace_notes_octaves(self, notes: list[Note], position: Position) -> list[Note]:
        """Updates the octave of any grace note found in measure. The octave is set by checking
            the note that follows the grace minimizing the 'interval' between both notes.

        Args:
            measure (list[Note]): list of notes that should be checked for grace notes.
        Raises:
            ValueError: if a grace note is not followed by a melodic note.
        Returns:
            list[Note]: Te updated llist
        """

        for pos, (note, nextnote) in enumerate(zip(notes.copy(), notes.copy()[1:] + [None])):
            if note.effect is Stroke.GRACE_NOTE and note.pitch in Tone.MELODIC_PITCHES:
                if not nextnote or not nextnote.pitch in Tone.MELODIC_PITCHES:
                    raise ValueError(
                        "Grace note not followed by melodic note in %s" % TremoloPatternGenerator.notes_to_str(notes)
                    )
                tones = Instrument.get_tones_within_range(note.to_tone(), position=position, match_octave=False)
                # pylint: disable=cell-var-from-loop
                nearest = sorted(tones, key=lambda x: abs(Instrument.interval(x, nextnote.to_tone())))[0]
                # pylint: enable=cell-var-from-loop
                nearest_grace_note = NoteFactory.clone_note(note, octave=nearest.octave)
                notes[pos] = nearest_grace_note
        return notes

    def fire(
        self, pass_: Measure.Pass, position: Position, all_positions: list[Position], metadata: list[MetaData]
    ) -> list[Note]:
        return self.update_grace_notes_octaves(notes=pass_.notes, position=position)
