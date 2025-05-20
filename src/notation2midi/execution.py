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


class GoTo(BaseModel):
    MAXPASSES: ClassVar[int] = 99
    cycle: int = MAXPASSES  # Determines when _pass_counter_ should be reset
    to_beat: dict[PassSequence, Beat] = Field(default_factory=dict)
    curr_pass: int = 0

    def reset_pass_counter(self) -> None:
        """(re-)initializes the pass counter"""
        self.curr_pass = 0

    def incr_pass_counter(self) -> None:
        """increments the pass counter. Resets the counter if required."""
        if self.curr_pass >= self.cycle:
            self.reset_pass_counter()
        self.curr_pass += 1

    @property
    def max_passnr(self) -> PassSequence:
        return max(list(self.to_beat.keys()) + [0])

    def next_beat(self) -> Beat:
        return self.to_beat.get(self.curr_pass, self.to_beat.get(DEFAULT, None))


class Loop(BaseModel):
    iterations: int = 0
    first_beat: Beat = None
    last_beat: Beat = None
    curr_iteration: int = 0

    def reset_iteration_counter(self) -> None:
        """(re-)initializes the pass counter"""
        self.curr_iteration = 0

    def incr_iteration_counter(self) -> None:
        """increments the pass counter. Resets the counter if required."""
        self.curr_iteration += 1

    def next_beat(self, beat: Beat) -> Beat:
        return self.first_beat if beat is self.last_beat and self.curr_iteration < self.iterations else None


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
    goto: GoTo = Field(default_factory=GoTo)
    loop: Loop = None
    dynamics: Dynamics = Field(default_factory=Dynamics)
    tempo: Tempo = Field(default_factory=Tempo)

    def reset_all_counters(self) -> None:
        self.goto.reset_pass_counter()
        if self.loop:
            self.loop.reset_iteration_counter()

    def incr_all_counters(self) -> None:
        self.goto.incr_pass_counter()
        if self.loop:
            self.loop.incr_iteration_counter()

    def get_pass(self) -> PassSequence:
        return self.goto.curr_pass

    def get_iteration(self) -> IterationSequence:
        if self.loop:
            return self.loop.curr_iteration
        return DEFAULT

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
        return self.beat.get_pass_object(position=position, passid=self.goto.curr_pass)


class ExecutionManager:
    """Takes care of the execution or 'performance' of a score. This consists in applying dynamics, tempo
    and flow (GOTO, LOOP and SEQUENCE).

    Returns:
        _type_: _description_
    """

    def __init__(self):
        self.beat_execution_dict: dict[int, Execution] = {}
        self.gongan_execution_dict: dict[str, Execution] = {}

    def execution(self, beat: Beat) -> Execution:
        """Returns the execution information for the given beat."""
        key = beat.full_id
        if not key in self.beat_execution_dict:
            self.beat_execution_dict[key] = Execution(beat=beat)
        return self.beat_execution_dict[key]

    def gongan_execution(self, beat: Beat) -> Execution | None:
        """Returns the execution information of the given gongan."""
        key = beat.gongan_id
        if not key in self.gongan_execution_dict:
            self.gongan_execution_dict[key] = Execution()
        return self.gongan_execution_dict[key]

    def gonganid_execution(self, gongan_id: int) -> Execution | None:
        """Returns the execution information of the given gongan."""
        if not gongan_id in self.gongan_execution_dict:
            self.gongan_execution_dict[gongan_id] = Execution()
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
            if beat is gongan_exec.loop.last_beat:
                next_beat = gongan_exec.loop.next_beat(beat)
                if not next_beat:
                    # :End of loop: reset iteration counter
                    gongan_exec.loop.reset_iteration_counter()

        # Retrieve next beat from GoTo item
        if not next_beat:
            beat_exec = self.execution(beat)
            next_beat = beat_exec.goto.next_beat() or beat_exec.beat.next
        if next_beat:
            # Update the pass and iteration counters
            nb_gongan_exec = self.gongan_execution(next_beat)
            if nb_gongan_exec.loop:
                if next_beat is nb_gongan_exec.loop.first_beat:
                    nb_gongan_exec.loop.incr_iteration_counter()
                iteration_counter = nb_gongan_exec.loop.curr_iteration
            else:
                iteration_counter = None
            # Increment the pass counter of the next beat. In case of a loop, only increment the pass
            # counter on the first iteration.
            if not iteration_counter or iteration_counter == 1:
                self.execution(next_beat).goto.incr_pass_counter()
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
