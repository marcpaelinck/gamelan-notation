from dataclasses import dataclass, field
from typing import ClassVar, Optional

from pydantic import BaseModel, Field

from src.common.classes import Beat, FlowInfo, Gongan, MidiNote
from src.common.constants import (
    BPM,
    DEFAULT,
    IterationSequence,
    Octave,
    PassSequence,
    Pitch,
    Position,
    Stroke,
)
from src.notation2midi.metadata_classes import MetaData
from src.settings.classes import Part, RunSettings

# Next statement is to avoid pylint bug when assigning Field to attributes in pydantic class definition
# see bugreport https://github.com/pylint-dev/pylint/issues/10087
# pylint: disable=no-member


class Flow(BaseModel):
    MAXCYCLE: ClassVar[int] = 99
    cycle: int = MAXCYCLE  # Determines when _pass_counter_ should be reset
    from_beat: Beat
    to_beat_dict: dict[PassSequence, Beat] = Field(default_factory=dict)
    counter: int = 0

    def reset_counter(self) -> None:
        """(re-)initializes the pass counter"""
        self.counter = 0

    def incr_counter(self) -> int:
        """increments the pass counter. Resets the counter if required."""
        if self.counter >= self.cycle:
            self.reset_counter()
        self.counter += 1
        return self.counter

    @property
    def max_passnr(self) -> PassSequence:
        return max(list(self.to_beat_dict.keys()) + [0])

    def next_beat(self):
        """Override this method"""


class GoTo(Flow):
    def next_beat(self) -> Beat:
        return self.to_beat_dict.get(self.counter, self.to_beat_dict.get(DEFAULT, None))


class Loop(Flow):
    @property
    def to_beat(self):
        return self.to_beat_dict.get(DEFAULT, None)

    def next_beat(self, beat: Beat) -> Beat:
        return self.to_beat if beat is self.from_beat and self.counter < self.cycle else None


# `steps` attribute of Classes Tempo and Dynamics indicates a gradual change of tempo or dynamics.
# If step is 0, the value takes effect immediately. Otherwise the value will be incrementally
# changed over 'step' number of beats.


class Tempo(BaseModel):
    """Contains tempo information.
    See FlowType.is_expression() for a list of expression types.
    """

    steps: int = 0
    value_dict: dict[tuple[PassSequence, IterationSequence], int] = Field(default_factory=dict)

    def value(self, pass_: int = DEFAULT, iteration: int = DEFAULT):
        """Returns the dynamics value for the given combination of attributess"""
        return self.value_dict.get(
            (pass_, iteration),
            self.value_dict.get(
                (DEFAULT, iteration),
                self.value_dict.get((pass_, DEFAULT), self.value_dict.get((DEFAULT, DEFAULT), None)),
            ),
        )

    def update(  # pylint: disable=dangerous-default-value # [] is only iterated, not modifed
        self,
        value: int,
        *,
        passes: list[PassSequence] = [],
        iterations: list[IterationSequence] = [],
        steps: int = None,
    ) -> None:
        """Updates the value_dict"""
        # TODO: currently, steps will be overwritten. This should be OK for now.
        addition = {(pass_, iteration): value for pass_ in passes or [DEFAULT] for iteration in iterations or [DEFAULT]}
        self.value_dict |= addition
        if steps:
            self.steps = steps


class Dynamics(BaseModel):
    """Contains dynamics information.
    See FlowType.is_expression() for a list of expression types.
    Note: when creating an Expression object, the positions argument can be either a list of strings or its
    JSON representation. Both will be interpreted correctly by the Pydantic BaseModel.
    """

    steps: int = 0
    value_dict: dict[tuple[Position, PassSequence, IterationSequence], int] = Field(default_factory=dict)

    def value(self, position: Position, pass_: int = DEFAULT, iteration: int = DEFAULT):
        """Returns the dynamics value for the given combination of attributess"""
        return self.value_dict.get(
            (position, pass_, iteration),
            self.value_dict.get(
                (position, DEFAULT, iteration),
                self.value_dict.get(
                    (position, pass_, DEFAULT), self.value_dict.get((position, DEFAULT, DEFAULT), None)
                ),
            ),
        )

    def update(  # pylint: disable=dangerous-default-value # [] is only iterated, not modifed
        self,
        value: int,
        *,
        positions: list[Position],
        passes: list[PassSequence] = [],
        iterations: list[IterationSequence] = [],
        steps: int = None,
    ) -> None:
        """Updates the value_dict"""
        # TODO: currently, steps will be overwritten. This should be OK for now.
        addition = {
            (position, pass_, iteration): value
            for position in positions
            for pass_ in passes or [DEFAULT]
            for iteration in iterations or [DEFAULT]
        }
        self.value_dict |= addition
        if steps:
            self.steps = steps


class Execution(BaseModel):
    """Contains execution details of a single beat, such as tempo, dynamics, loops and 'go to' directives.
    Also contains the execution status (pass)"""

    beat: Optional[Beat] = None  # The beat to which this flow object belongs: value is set by Beat.model_post_init
    goto: GoTo = None
    loop: Loop = None
    dynamics: Dynamics = Field(default_factory=Dynamics)
    tempo: Tempo = Field(default_factory=Tempo)

    def model_post_init(self, context):
        if self.beat:
            self.goto = GoTo(from_beat=self.beat)
            self.goto.to_beat_dict[DEFAULT] = self.beat.next
        return super().model_post_init(context)

    def reset_all_counters(self) -> None:
        if self.goto:
            self.goto.reset_counter()
        if self.loop:
            self.loop.reset_counter()

    def incr_all_counters(self) -> None:
        if self.goto:
            self.goto.incr_counter()
        if self.loop:
            self.loop.incr_counter()

    def get_pass(self) -> PassSequence:
        return self.goto.counter if self.goto else DEFAULT

    def get_iteration(self) -> IterationSequence:
        return self.loop.counter if self.loop else DEFAULT

    def get_dynamics(self, curr_dynamics: int, position: Position, pass_: int, iteration: int = DEFAULT) -> int | None:
        """Returns either a Velocity value for the current beat.
        Returns None if the value for the current beat is the same as that of the previous beat.
        In case of a gradual change over several measures, calculates the value for the current beat.
        """
        value = self.dynamics.value(position=position, pass_=pass_, iteration=iteration)
        if value and self.dynamics.steps > 1:
            value = curr_dynamics + int((value - curr_dynamics) / self.dynamics.steps)
        return value

    def get_tempo(self, curr_tempo, pass_: int, iteration: int = DEFAULT) -> int | None:
        """Returns a BPM value for the current beat.
        Returns None if the value for the current beat is the same as that of the previous beat.
        In case of a gradual change over several measures, calculates the value for the current beat.
        """
        value = self.tempo.value(pass_=pass_, iteration=iteration)
        if value and self.tempo.steps > 1:
            value = curr_tempo + int((value - curr_tempo) / self.tempo.steps)
        return value

    def get_curr_pass_object(self, position: Position):
        """Returns the current pass in the flow

        Args:
            position (Position): _description_

        Returns:
            _type_: _description_
        """
        return self.beat.get_pass_object(position=position, passid=self.goto.counter)


class ExecutionManager:
    """Takes care of the execution or 'performance' of a score. This consists in applying dynamics, tempo
    and flow (GOTO, LOOP and SEQUENCE).

    Returns:
        _type_: _description_
    """

    def __init__(self):
        self.beat_execution_dict: dict[int, Execution] = {}
        self.gongan_execution_dict: dict[str, Execution] = {}

    def add_beat_execution(self, beat: Beat) -> None:
        """Adds an Execution to the beat_execution_dict for the given beat"""
        self.beat_execution_dict[beat.full_id] = Execution(beat=beat)

    def add_gongan_execution(self, gongan_id: int) -> None:
        """Adds an Execution to the gongan_execution_dict for the given gongan id"""
        self.gongan_execution_dict[gongan_id] = Execution()

    def execution(self, beat: Beat) -> Execution:
        """Returns the execution information for the given beat."""
        if not beat.full_id in self.beat_execution_dict:
            self.add_beat_execution(beat)
        return self.beat_execution_dict[beat.full_id]

    def gongan_execution(self, beat: Beat) -> Execution | None:
        """Returns the execution information of the given gongan."""
        if not beat.gongan_id in self.gongan_execution_dict:
            self.add_gongan_execution(beat.gongan_id)
        return self.gongan_execution_dict[beat.gongan_id]

    def gonganid_execution(self, gongan_id: int) -> Execution | None:
        """Returns the execution information of the given gongan."""
        if not gongan_id in self.gongan_execution_dict:
            self.add_gongan_execution(gongan_id)
        return self.gongan_execution_dict[gongan_id]

    def get_curr_pass(self, beat: Beat):
        beat_exec = self.execution(beat)
        return beat_exec.get_pass()

    def get_curr_iteration(self, beat: Beat):
        gongan_exec = self.gongan_execution(beat)
        return gongan_exec.get_iteration()

    def reset_all_counters(self):
        for execution in self.beat_execution_dict.values():
            execution.reset_all_counters()
        for execution in self.gongan_execution_dict.values():
            execution.reset_all_counters()

    def next_beat_in_flow(self, beat: Beat) -> Beat:
        """Determines the next beat, based on flow information and the current status
        of the execution (specifically the pass sequence for the given beat).
        Args:
            beat (Beat): beat from which to determine the next beat to be executed
        Returns:
            Beat: _description_
        """
        gongan_exec = self.gongan_execution(beat)
        next_beat = None
        if gongan_exec.loop:
            # Retrieve next beat from Loop item (returns None if there are no more iterations)
            if beat is gongan_exec.loop.from_beat:
                # Start with next iteration
                next_beat = gongan_exec.loop.next_beat(beat)
                # if not next_beat:
                #     # No more iterations: reset iteration counter
                #     gongan_exec.loop.reset_iteration_counter()

        # Retrieve next beat: either GoTo item or default next beat
        if not next_beat:
            beat_exec = self.execution(beat)
            if beat_exec.goto:
                next_beat = beat_exec.goto.next_beat()
            if not next_beat:
                next_beat = beat_exec.beat.next
        if next_beat:
            # Update the pass and iteration counters
            nb_gongan_exec = self.gongan_execution(next_beat)
            if nb_gongan_exec.loop:
                if next_beat is nb_gongan_exec.loop.to_beat:
                    nb_gongan_exec.loop.incr_counter()
                iteration_counter = nb_gongan_exec.loop.counter
            else:
                iteration_counter = None
            # Increment the pass counter of the next beat. In case of a loop, only increment the pass
            # counter on the first iteration.
            if (not iteration_counter or iteration_counter == 1) and self.execution(next_beat).goto:
                self.execution(next_beat).goto.incr_counter()
            # Increment the iteration counter of the next beat's gongan it is
            # the first beat of a gongan that has a loop.
        return next_beat

    def get_tempo(self, beat: Beat, curr_tempo: BPM):
        curr_pass = self.get_curr_pass(beat)
        curr_iteration = self.get_curr_iteration(beat)
        return self.execution(beat).get_tempo(curr_tempo=curr_tempo, pass_=curr_pass, iteration=curr_iteration)

    def get_dynamics(self, beat: Beat, position: Position, curr_dynamics: int):
        curr_pass = self.get_curr_pass(beat)
        curr_iteration = self.get_curr_iteration(beat)
        return self.execution(beat).get_dynamics(
            curr_dynamics=curr_dynamics, position=position, pass_=curr_pass, iteration=curr_iteration
        )


@dataclass
class Score:
    title: str
    settings: RunSettings
    instrument_positions: set[Position] = None
    gongans: list[Gongan] = field(default_factory=list)
    global_metadata: list[MetaData] = field(default_factory=list)
    global_comments: list[str] = field(default_factory=list)
    midi_notes_dict: dict[tuple[Position, Pitch, Octave, Stroke], MidiNote] = None
    flowinfo: FlowInfo = field(default_factory=FlowInfo)
    midifile_duration: int = None
    part_info: Part = None
    execution_manager: ExecutionManager = None
