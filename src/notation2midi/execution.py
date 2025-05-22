from dataclasses import dataclass, field
from typing import ClassVar

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
    to_beat_dict: dict[PassSequence, Beat | None] = Field(default_factory=dict)
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
    """Contains tempo information."""

    steps: int = 0
    value_dict: dict[tuple[PassSequence, IterationSequence], int] = Field(default_factory=dict)

    def value(self, curr_tempo: int, pass_: int = DEFAULT, iteration: int = DEFAULT):
        """Returns the dynamics value for the given combination of attributess"""
        value = self.value_dict.get(
            (pass_, iteration),
            self.value_dict.get(
                (DEFAULT, iteration),
                self.value_dict.get((pass_, DEFAULT), self.value_dict.get((DEFAULT, DEFAULT), None)),
            ),
        )
        if value and self.steps > 1:
            value = curr_tempo + int((value - curr_tempo) / self.steps)
        return value

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
    """Contains dynamics information."""

    steps: int = 0
    value_dict: dict[tuple[Position, PassSequence, IterationSequence], int] = Field(default_factory=dict)

    def value(self, curr_dynamics: int, position: Position, pass_: int = DEFAULT, iteration: int = DEFAULT):
        """Returns the dynamics value for the given combination of attributess"""
        value = self.value_dict.get(
            (position, pass_, iteration),
            self.value_dict.get(
                (position, DEFAULT, iteration),
                self.value_dict.get(
                    (position, pass_, DEFAULT), self.value_dict.get((position, DEFAULT, DEFAULT), None)
                ),
            ),
        )
        if value and self.steps > 1:
            value = curr_dynamics + int((value - curr_dynamics) / self.steps)
        return value

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


BeatID = str
GonganID = int


@dataclass
class ExecutionManager:
    """Takes care of the execution or 'performance' of a score. This consists in applying dynamics, tempo
    and flow (GOTO, LOOP and SEQUENCE).

    Returns:
        _type_: _description_
    """

    goto_dict: dict[BeatID, GoTo] = field(default_factory=dict)
    loop_dict: dict[GonganID, Loop] = field(default_factory=dict)
    dynamics_dict: dict[BeatID, Dynamics] = field(default_factory=dict)
    tempo_dict: dict[BeatID, Tempo] = field(default_factory=dict)

    def add_beat_execution(self, beat: Beat) -> None:
        """Adds an Execution to the beat_execution_dict for the given beat"""
        # self.beat_execution_dict[beat.full_id] = Execution(beat=beat)

    def add_gongan_execution(self, gongan_id: int) -> None:
        """Adds an Execution to the gongan_execution_dict for the given gongan id"""
        # self.gongan_execution_dict[gongan_id] = Execution()

    def goto(self, beat: Beat, create_if_none: bool = True) -> GoTo:
        """Returns the GoTo object for the beat or a newly created default GoTo value"""
        goto = self.goto_dict.get(beat.full_id, None)
        if not goto and create_if_none:
            goto = GoTo(from_beat=beat, to_beat_dict={DEFAULT: beat.next})
            self.goto_dict[beat.full_id] = goto
        return goto

    def set_goto(self, beat: Beat, goto: GoTo) -> None:
        self.goto_dict[beat.full_id] = goto

    def extend_goto(self, beat: Beat, goto: GoTo, skip_default=True) -> None:
        """extend the beat's goto with the goto data.
        Does not process the goto's default value"""
        self.goto(beat).to_beat_dict |= {
            key: val for key, val in goto.to_beat_dict.items() if not skip_default or key != DEFAULT
        }

    def loop(self, beat: Beat, create_if_none: bool = False) -> Loop | None:
        """Returns the Loop object for the beat or None"""
        loop = self.loop_dict.get(beat.gongan_id, None)
        if not loop and create_if_none:
            loop = Loop()
            self.loop_dict[beat.gongan_id] = loop
        return loop

    def set_loop(self, gongan_id: GonganID, loop: Loop) -> None:
        """Assigns a Loop object for the given gongan"""
        self.loop_dict[gongan_id] = loop

    def dynamics(self, beat: Beat, create_if_none: bool = False) -> Dynamics | None:
        """Returns the Loop object for the beat or None"""
        dynamics = self.dynamics_dict.get(beat.full_id, None)
        if not dynamics and create_if_none:
            dynamics = Dynamics()
            self.dynamics_dict[beat.full_id] = dynamics
        return dynamics

    def set_dynamics(self, beat: Beat, dynamics: Dynamics) -> None:
        """Assigns a Dynamics object for the given beat"""
        self.dynamics_dict[beat.full_id] = dynamics

    def tempo(self, beat: Beat, create_if_none: bool = False) -> Tempo | None:
        """Returns the Loop object for the beat or None"""
        tempo = self.tempo_dict.get(beat.full_id, None)
        if not tempo and create_if_none:
            tempo = Tempo()
            self.tempo_dict[beat.full_id] = tempo
        return tempo

    def set_tempo(self, beat: Beat, tempo: Tempo) -> None:
        """Assigns a Tempo object for the given beat"""
        self.tempo_dict[beat.full_id] = tempo

    def get_curr_pass(self, beat: Beat) -> int:
        return self.goto(beat).counter

    def get_curr_iteration(self, beat: Beat) -> int | None:
        if self.loop(beat):
            return self.loop(beat).counter
        return DEFAULT

    def reset_all_counters(self):
        """Resets all GoTo and Loop counters"""
        for goto in self.goto_dict.values():
            goto.reset_counter()
        for loop in self.loop_dict.values():
            loop.reset_counter()

    def next_beat_in_flow(self, beat: Beat) -> Beat:
        """Determines the next beat, based on flow information and the current status
        of the execution (specifically the pass sequence for the given beat).
        Args:
            beat (Beat): beat from which to determine the next beat to be executed
        Returns:
            Beat: _description_
        """
        next_beat = None
        if loop := self.loop(beat):
            # Retrieve next beat from Loop item (returns None if there are no more iterations)
            if beat is loop.from_beat:
                # Start with next iteration
                next_beat = loop.next_beat(beat)

        # Retrieve next beat: note that goto contains default value for next beat
        if not next_beat:
            next_beat = self.goto(beat).next_beat()
        if next_beat:
            # Increment the loop counter if the next beat starts a new iteration
            if nb_loop := self.loop(next_beat):
                if next_beat is nb_loop.to_beat:
                    nb_loop.incr_counter()
                iteration_counter = nb_loop.counter
            else:
                iteration_counter = None
            # Increment the pass counter of the next beat. If the gongan has a loop,
            # only increment the pass counter on the first iteration.
            if (not iteration_counter or iteration_counter == 1) and self.goto(next_beat):
                self.goto(next_beat).incr_counter()
        return next_beat

    def get_tempo(self, beat: Beat, curr_tempo: BPM):
        """Returns the tempo for the given beat."""
        if not (tempo := self.tempo(beat)):
            return curr_tempo
        curr_pass = self.get_curr_pass(beat)
        curr_iteration = self.get_curr_iteration(beat)
        return tempo.value(curr_tempo=curr_tempo, pass_=curr_pass, iteration=curr_iteration)

    def get_dynamics(self, beat: Beat, position: Position, curr_dynamics: int):
        """Returns the dynamics for the given beat and position."""
        if not (dynamics := self.dynamics(beat)):
            return curr_dynamics
        curr_pass = self.get_curr_pass(beat)
        curr_iteration = self.get_curr_iteration(beat)
        return dynamics.value(curr_dynamics=curr_dynamics, position=position, pass_=curr_pass, iteration=curr_iteration)


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
