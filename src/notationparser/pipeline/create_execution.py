from typing import override

from src.common.classes import Beat, Gongan, Score
from src.common.constants import DEFAULT
from src.notationparser.classes import Agent
from src.notationparser.execution.execution import ExecutionManager, Loop
from src.notationparser.metadata_classes import (
    AutoKempyungMeta,
    CopyMeta,
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
        self.execution_mgr = ExecutionManager(score=self.score)

    @override
    @classmethod
    def run_condition_satisfied(cls, run_settings: RunSettings):
        return run_settings.options.notation_to_midi

    def create_default_gotos(self):
        """Creates a goto execution from each beat to its 'next' beat (default flow)."""
        for gongan in self.score.gongans:
            for beat in gongan.beats:
                self.execution_mgr.create_default_goto(beat)

    def process_goto(
        self, frombeat: Beat, tobeat: Beat, passes: list[int] | None = None, cycle: int | None = None
    ) -> None:
        tobeat_dict = {passnr: tobeat for passnr in passes} if passes else {DEFAULT: tobeat}
        self.execution_mgr.goto(frombeat).to_beat_dict |= tobeat_dict
        if cycle:
            self.execution_mgr.goto(frombeat).cycle = cycle

    def _process_sequence_metadata(self):
        """Translates the labels of the SEQUENCE metadata into goto directives in the respective beats."""
        for initial_gongan, sequence in self.score.flowinfo.sequences:
            gongan = initial_gongan
            for label in sequence.value:
                from_beat = gongan.beats[-1]  # Sequence always links last beat to first beat of next gongan in the list
                to_beat = self.score.flowinfo.labels[label]
                # Select next available pass
                goto = self.execution_mgr.goto(from_beat)
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

        for meta in sorted(sum(gongan.metadata.values(), []), key=lambda x: x.processingorder):
            self.curr_line_nr = meta.line
            match meta:
                case GoToMeta():
                    # Add goto info to the beat
                    if self.score.flowinfo.labels.get(meta.label, None):
                        process_goto_meta(gongan, meta)
                    else:
                        # Label not yet encountered: store GoTo obect in flowinfo
                        self.score.flowinfo.gotos[meta.label].append((gongan, meta))
                case LoopMeta():
                    self.execution_mgr.set_loop(
                        gongan.id,
                        Loop(
                            from_beat=gongan.beats[-1],
                            to_beat_dict={DEFAULT: gongan.beats[0]},
                            cycle=meta.count,
                            passes=meta.passes or [],
                        ),
                    )
                case SequenceMeta():
                    self.score.flowinfo.sequences.append((gongan, meta))
                case TempoMeta() | DynamicsMeta():
                    # Check if the beat start and count parameters match with the gongan length
                    if (
                        first_too_large := meta.first_beat > len(gongan.beats)
                    ) or meta.first_beat + meta.beat_count - 1 > len(gongan.beats):
                        value = "first_beat" + (" + beat_count" if not first_too_large else "")
                        self.logerror("%s metadata: %s is larger than the number of beats" % (meta.metatype, value))
                        continue
                    beat = gongan.beats[meta.first_beat_seq]
                    if isinstance(meta, DynamicsMeta):
                        self.execution_mgr.assign_dynamics(beat=beat, meta=meta)
                    elif isinstance(meta, TempoMeta):
                        self.execution_mgr.assign_tempo(beat=beat, meta=meta)
                case (
                    AutoKempyungMeta()
                    | GonganMeta()
                    | KempliMeta()
                    | LabelMeta()
                    | OctavateMeta()
                    | PartMeta()
                    | SuppressMeta()
                    | CopyMeta()
                    | ValidationMeta()
                    | WaitMeta()
                ):
                    # Processed by ScoreCreatorAgent.
                    # We mention these classes here to be sure that all metadata types are taken into account.
                    pass
                case _:
                    raise ValueError("Metadata type %s is not supported." % type(meta).__name__)

    @override
    def _main(self) -> ExecutionManager:
        self.create_default_gotos()

        for gongan in self.gongan_iterator(self.score):
            self._apply_metadata(gongan)
        self._process_sequence_metadata()
        return self.execution_mgr
