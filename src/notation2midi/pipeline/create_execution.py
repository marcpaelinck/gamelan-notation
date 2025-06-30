from typing import override

from src.common.classes import Beat, Gongan, Score
from src.common.constants import DEFAULT
from src.notation2midi.classes import Agent
from src.notation2midi.execution.execution import Execution, Loop
from src.notation2midi.metadata_classes import (
    AutoKempyungMeta,
    DynamicsMeta,
    GonganMeta,
    GoToMeta,
    KempliMeta,
    LabelMeta,
    LoopMeta,
    OctavateMeta,
    PartMeta,
    SequenceMeta,
    SuppressMeta,
    TempoMeta,
    ValidationMeta,
    WaitMeta,
)
from src.settings.classes import RunSettings


class ExecutionCreatorAgent(Agent):
    """Creates an Execution object that contains the interpretation of the score.
    See Execution class for more information.
    """

    LOGGING_MESSAGE = "CREATING SCORE EXECUTION"
    EXPECTED_INPUT_TYPES = (Agent.InputOutputType.COMPLETESCORE,)
    RETURN_TYPE = Agent.InputOutputType.EXECUTION

    score: Score

    def __init__(self, complete_score: Score):
        super().__init__(complete_score.settings)
        self.score = complete_score
        self.execution = Execution(score=self.score)

    @override
    @classmethod
    def run_condition_satisfied(cls, run_settings: RunSettings):
        return run_settings.options.notation_to_midi

    def create_default_gotos(self):
        for gongan in self.score.gongans:
            for beat in gongan.beats:
                self.execution.create_default_goto(beat)

    def process_goto(
        self, frombeat: Beat, tobeat: Beat, passes: list[int] | None = None, cycle: int | None = None
    ) -> None:
        tobeat_dict = {passnr: tobeat for passnr in passes} if passes else {DEFAULT: tobeat}
        self.execution.goto(frombeat).to_beat_dict |= tobeat_dict
        if cycle:
            self.execution.goto(frombeat).cycle = cycle

    def _process_sequences(self):
        """Translates the labels of the SEQUENCE metadata into goto directives in the respective beats."""
        for initial_gongan, sequence in self.score.flowinfo.sequences:
            gongan = initial_gongan
            for label in sequence.value:
                from_beat = gongan.beats[-1]  # Sequence always links last beat to first beat of next gongan in the list
                to_beat = self.score.flowinfo.labels[label]
                # TODO GOTO modify, also for frequency = ALWAYS
                # TODO GOTO remove next line
                # pass_nr = max([p for p in from_beat.flow.goto.keys()] or [0]) + 1  # Select next available pass
                # Select next available pass
                goto = self.execution.goto(from_beat)
                pass_nr = goto.max_passnr + 1
                # TODO: check if this works
                self.process_goto(frombeat=from_beat, tobeat=to_beat, passes=[pass_nr])
                gongan = self.score.gongans[to_beat.gongan_seq]

    def _apply_metadata(self, gongan: Gongan) -> None:
        """Processes the metadata of a gongan into the object model.

        Args:
            metadata (list[MetaData]): The metadata to process.
            gongan (Gongan): The gongan to which the metadata applies.
        """

        def process_goto_meta(gongan: Gongan, gotometa: GoToMeta) -> None:
            # for rep in gotometa.passes:
            self.process_goto(
                frombeat=gongan.beats[gotometa.beat_seq],
                tobeat=self.score.flowinfo.labels[gotometa.label],
                passes=gotometa.passes,
                cycle=gotometa.cycle,
            )

        metadata = gongan.metadata.copy() + self.score.global_metadata
        haslabel = False  # Will be set to true if the gongan has a metadata Label tag.
        for meta in sorted(metadata, key=lambda x: x.processingorder):
            self.curr_line_nr = meta.line
            match meta:
                case GoToMeta():
                    # Add goto info to the beat
                    if self.score.flowinfo.labels.get(meta.label, None):
                        process_goto_meta(gongan, meta)
                    else:
                        # Label not yet encountered: store GoTo obect in flowinfo
                        self.score.flowinfo.gotos[meta.label].append((gongan, meta))
                case LabelMeta():
                    # Add the label to flowinfo
                    # TODO move this to Execution
                    haslabel = True
                    self.score.flowinfo.labels[meta.name] = gongan.beats[meta.beat_seq]
                    # Process any GoToMeta pointing to this label
                    gotometa: GoToMeta
                    for gongan_, gotometa in self.score.flowinfo.gotos[meta.name]:
                        process_goto_meta(gongan_, gotometa)
                case LoopMeta():
                    self.execution.set_loop(
                        gongan.id,
                        Loop(from_beat=gongan.beats[-1], to_beat_dict={DEFAULT: gongan.beats[0]}, cycle=meta.count),
                    )
                case SequenceMeta():
                    self.score.flowinfo.sequences.append((gongan, meta))
                case TempoMeta() | DynamicsMeta():
                    is_dynamics = isinstance(meta, DynamicsMeta)
                    # Check if the beat start and count parameters match with the gongan length
                    if (
                        first_too_large := meta.first_beat > len(gongan.beats)
                    ) or meta.first_beat + meta.beat_count - 1 > len(gongan.beats):
                        value = "first_beat" + (" + beat_count" if not first_too_large else "")
                        self.logerror(f"{meta.metatype} metadata: {value} is larger than the number of beats")
                        continue
                    beat = gongan.beats[meta.first_beat_seq]
                    if meta.beat_count == 0:
                        # immediate change.
                        if is_dynamics:
                            self.execution.dynamics(beat, True).update(
                                value=meta.value,
                                positions=meta.positions,
                                passes=meta.passes,
                                iterations=meta.iterations,
                            )
                        else:
                            self.execution.tempo(beat, True).update(
                                value=meta.value, passes=meta.passes, iterations=meta.iterations
                            )
                    else:
                        # Gradual change over meta.beats beats. The first change is after first beat.
                        # This emulates a gradual tempo change.
                        for steps in range(meta.beat_count, 0, -1):
                            beat = beat.next
                            if not beat:  # End of score. This should not happen unless notation error.
                                break
                            if is_dynamics:
                                self.execution.dynamics(beat, True).update(
                                    value=meta.value,
                                    positions=meta.positions,
                                    passes=meta.passes,
                                    iterations=meta.iterations,
                                    steps=steps,
                                )
                            else:
                                self.execution.tempo(beat, True).update(
                                    value=meta.value,
                                    passes=meta.passes,
                                    iterations=meta.iterations,
                                    steps=steps,
                                )
                case (
                    AutoKempyungMeta()
                    | GonganMeta()
                    | KempliMeta()
                    | OctavateMeta()
                    | PartMeta()
                    | SuppressMeta()
                    | ValidationMeta()
                    | WaitMeta()
                ):
                    # Processed by ScoreCreatorAgent.
                    # We mention these classes here to be sure that all metadata types are taken into account.
                    pass
                case _:
                    raise ValueError("Metadata type %s is not supported." % type(meta).__name__)

        # TODO Think the following part over. It might cause unexpected results. But omitting it might puzzle the users
        # because then the dynamics and tempo will be taken from whatever gongan precedes the current one.
        # It might be good discipline to always explicitly set dynamics and tempo for gongans that have a label. The application
        # might give a warning if they are missing and suggest to add them.
        # TODO suppressed because it gives unexpected results
        if haslabel:
            # Gongan has one or more Label metadata items: explicitly set the current tempo for each beat by copying it
            # from its predecessor. This will ensure that a goto to any of these beats will pick up the correct tempo.
            for beat in gongan.beats:
                if beat.prev and beat.prev.gongan_id == gongan.id:
                    if (
                        not self.execution.dynamics(beat) or not self.execution.dynamics(beat).value_dict
                    ) and self.execution.dynamics(beat.prev):
                        self.execution.set_dynamics(beat, self.execution.dynamics(beat.prev).model_copy())
                    if (
                        not self.execution.tempo(beat) or not self.execution.tempo(beat).value_dict
                    ) and self.execution.tempo(beat.prev):
                        self.execution.set_tempo(beat, self.execution.tempo(beat.prev).model_copy())

    @override
    def _main(self) -> Execution:
        self.create_default_gotos()

        for gongan in self.gongan_iterator(self.score):
            self._apply_metadata(gongan)
        # Process the sequences metadata
        self._process_sequences()
        return self.execution
