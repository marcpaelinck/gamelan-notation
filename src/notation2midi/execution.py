from dataclasses import dataclass, field
from typing import ClassVar, Optional

from pydantic import BaseModel, Field

from src.common.classes import Beat, FlowInfo, Gongan, MidiNote
from src.common.constants import (
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
    iterations: int
    to_beat: Beat
    curr_iteration: int = 0

    def reset_iteration_counter(self) -> None:
        """(re-)initializes the pass counter"""
        self.curr_iteration = 0

    def incr_iteration_counter(self) -> None:
        """increments the pass counter. Resets the counter if required."""
        self.curr_iteration += 1

    def next_beat(self) -> Beat:
        return self.to_beat if self.curr_iteration < self.iterations else None


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
    """Contains execution details of a beat such as tempo, dynamics, loops and 'go to' directives."""

    beat: Optional[Beat] = None  # The beat to which this flow object belongs: value is set by Beat.model_post_init
    goto: GoTo = Field(default_factory=GoTo)
    loop: Loop | None = None
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

    def get_changed_dynamics(self, curr_dynamics: int, position: Position) -> int | None:
        """Returns either a Velocity value for the current beat.
        Returns None if the value for the current beat is the same as that of the previous beat.
        In case of a gradual change over several measures, calculates the value for the current beat.
        """
        if self.dynamics:
            value = self.dynamics.value(position=position, pass_=self.get_pass(), iteration=self.get_iteration())
            if value is None or value == curr_dynamics:
                return None
        if self.dynamics.steps > 1:
            value = curr_dynamics + int((value - curr_dynamics) / self.dynamics.steps)
        if value != curr_dynamics:
            return value
        return None

    def get_changed_tempo(self, curr_tempo) -> int | None:
        """Returns a BPM value for the current beat.
        Returns None if the value for the current beat is the same as that of the previous beat.
        In case of a gradual change over several measures, calculates the value for the current beat.
        """
        if self.tempo:
            value = self.tempo.value(pass_=self.get_pass(), iteration=self.get_iteration())
            if value is None or value == curr_tempo:
                return None
        if self.tempo.steps > 1:
            value = curr_tempo + int((value - curr_tempo) / self.tempo.steps)
        if value != curr_tempo:
            return value
        return None

    def get_curr_pass_object(self, position: Position):
        """Returns the current pass in the flow

        Args:
            position (Position): _description_

        Returns:
            _type_: _description_
        """
        return self.beat.get_pass_object(position=position, passid=self.goto.curr_pass)


class ExecutionManager:
    # gongans: list[Gongan] = None
    execution_dict: dict[str, Execution]

    def __init__(self):
        self.execution_dict = dict()

    def execution(self, beat: Beat) -> Execution:
        key = beat.full_id
        if not key in self.execution_dict:
            self.execution_dict[key] = Execution(beat=beat)
        return self.execution_dict[key]

    def next_beat_in_flow(self, beat: Beat) -> Beat:
        beat_exec = self.execution(beat)
        if beat_exec.loop:
            # Retrieve next beat from loop if the loop is still active
            if next_beat := beat_exec.loop.next_beat():
                if next_beat is beat:
                    beat_exec.loop.incr_iteration_counter()
                return next_beat
            # Otherwise reset the loop counter (for next pass if any)
            beat_exec.loop.reset_iteration_counter()
        # Retrieve next beat from GoTo item
        next_beat = beat_exec.goto.next_beat() or beat_exec.beat.next
        if next_beat:
            self.execution(next_beat).incr_all_counters()
        return next_beat


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
