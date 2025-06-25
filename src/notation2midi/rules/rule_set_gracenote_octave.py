from src.common.classes import Beat
from src.common.constants import Modifier, Position, Stroke
from src.common.notes import NoteFactory, Tone
from src.notation2midi.note_patterns import NotePattern, NotePatternGenerator
from src.notation2midi.rules.rule_cast_to_position import RuleCastToPosition
from src.notation2midi.rules.rules import Rule


class RuleSetGracenoteOctave(Rule):

    def update_grace_notes_octaves(self, beat: Beat, position: Position, passnr: int) -> list[NotePattern]:
        """Updates the octave of any grace note found in measure. The octave is set by checking
            the note that follows the grace minimizing the 'interval' between both notes.

        Args:
            measure (list[Note]): list of notes that should be checked for grace notes.
        Raises:
            ValueError: if a grace note is not followed by a melodic note.
        Returns:
            list[Note]: Te updated llist
        """

        notes = beat.measures[position].passes[passnr].boundnotes

        for pos, (note, nextnote) in enumerate(zip(notes.copy(), notes.copy()[1:] + [None])):
            if note.stroke is Stroke.GRACE_NOTE and note.pitch in Tone.MELODIC_PITCHES:
                if not nextnote or not nextnote.pitch in Tone.MELODIC_PITCHES:
                    raise ValueError(
                        "Grace note not followed by melodic note in %s" % NotePatternGenerator.notes_to_str(notes)
                    )
                tones = RuleCastToPosition.get_tones_within_range(note.to_tone(), position, match_octave=False)
                # pylint: disable=cell-var-from-loop
                nearest = sorted(tones, key=lambda x: abs(RuleCastToPosition.interval(x, nextnote.to_tone())))[0]
                # pylint: enable=cell-var-from-loop
                nearest_grace_note = NoteFactory.clone_bound_note(note, octave=nearest.octave)
                notes[pos] = nearest_grace_note
        return notes
