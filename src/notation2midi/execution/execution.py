from collections import defaultdict
from dataclasses import dataclass, field
from enum import StrEnum
from typing import ClassVar

from pydantic import BaseModel, Field

from src.common.classes import Beat, Score
from src.common.constants import DEFAULT, PassSequence, Position
from src.common.notes import Note
from src.notation2midi.metadata_classes import DynamicsMeta, TempoMeta

# Next statement is to avoid pylint bug when assigning Field to attributes in pydantic class definition
# see bugreport https://github.com/pylint-dev/pylint/issues/10087
# pylint: disable=no-member


class Flow(BaseModel):
    """Generic class that describes the sequence in which beats should be executed.
    The cycle variable enables to define cyclic flows, such as 'go to beat x on every third pass'"""

    MAXCYCLE: ClassVar[int] = 99  # Maximum value for a cycle
    cycle: int = MAXCYCLE  # Determines when counter should be reset
    from_beat: Beat
    # Contains the next beat as a function of the pass sequence number.
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
        """Returns the highest pass number in the to_beat_dict"""
        return max(list(self.to_beat_dict.keys()) + [0])

    def next_beat(self):
        """Override this method.
        Determines the next beat to be executed given the current flow status"""


class GoTo(Flow):
    def next_beat(self) -> Beat:
        return self.to_beat_dict.get(self.counter, self.to_beat_dict.get(DEFAULT, None))


class Loop(Flow):
    @property
    def to_beat(self):
        return self.to_beat_dict.get(DEFAULT, None)

    def next_beat(self, beat: Beat) -> Beat:  # pylint: disable=arguments-differ
        return self.to_beat if beat is self.from_beat and self.counter < self.cycle else None


@dataclass
class GradualChangeStatus:
    """Keeps track of the current status of a gradual change instruction (see below)."""

    initial_value: int = 0  # Value before the start of the change.
    beat_seq: int = 0  # current beat sequence (1..tot_beats)
    tot_beats: int = 0  # total number of beats involved in the gradual change.
    start_value: int = 0  # value at the start of the beat.
    end_value: int = 0  # (incremented) value at the end of the beat

    def completed(self):
        """Indicates whether the last change step has been executed"""
        return self.beat_seq >= self.tot_beats and self.start_value == self.end_value


class GradualChangeInstruction(BaseModel):
    """Generic class for instructions that describe a value change over multiple beats (e.g. Tempo or Dynamics).
    Each instruction corresponds with a metadata item and is linked to the first beat of the change sequence.
    Note that no initial value is given for the change sequence because it can only be determined
    when the flow is being processed."""

    positions: list[Position] = Field(default_factory=list)  # positions for which the instruction applies.
    passes: list[int] = Field(default_factory=list)
    iterations: list[int] = Field(default_factory=list)
    tot_beats: int = 0  # total number of beats involved in the gradual change.
    #                     If 0, the value should take effect immediately.
    target_value: int = 0  # The final value.
    status: GradualChangeStatus | None = None  # Current status of the change

    def matches(self, position: Position, pass_nr: int, iteration_nr: int):
        return (
            (not self.positions or position in self.positions)
            and (not self.passes or pass_nr in self.passes)
            and (not self.iterations or iteration_nr in self.iterations)
        )

    def clear_status(self):
        self.status = None

    def initialize_status(self, initial_value):
        """Initializes the gradual change. If tot_beats is 0, set start and end to the target value"""
        self.status = GradualChangeStatus(
            initial_value=initial_value,
            tot_beats=self.tot_beats,
            start_value=self.target_value if self.tot_beats == 0 else initial_value,
            end_value=self.target_value if self.tot_beats == 0 else initial_value,
        )

    def next_step(self) -> None:
        """Sets the status to the next step in the gradual change."""
        if self.status.completed():
            return
        self.status.beat_seq += 1
        if self.status.beat_seq > self.tot_beats:
            self.status.start_value = self.status.end_value = self.target_value
        elif self.status.beat_seq == self.tot_beats:
            self.status.start_value = self.status.end_value
            self.status.end_value = self.target_value
        else:
            self.status.start_value = self.status.end_value
            # self.status.end_value += round(((self.target_value - self.status.initial_value) / self.tot_beats))
            self.status.end_value = self.status.start_value + int(
                (self.target_value - self.status.start_value) / (self.tot_beats - self.status.beat_seq + 1)
            )
            x = 1


BeatID = str
GonganID = int


@dataclass
class ExecutionManager:
    """Takes care of the execution or 'performance' of a score. This consists in applying dynamics, tempo
    and flow (GOTO, LOOP and SEQUENCE).

    Returns:
        _type_: _description_
    """

    class GradualChangeType(StrEnum):
        TEMPO = "TEMPO"
        DYNAMICS = "DYNAMICS"

    score: Score
    curr_beat: Beat = None
    curr_position: Position = None
    goto_dict: dict[BeatID, GoTo] = field(default_factory=dict)
    loop_dict: dict[GonganID, Loop] = field(default_factory=dict)
    dynamics_dict: dict[BeatID, list[GradualChangeInstruction]] = field(default_factory=lambda: defaultdict(list))
    tempo_dict: dict[BeatID, list[GradualChangeInstruction]] = field(default_factory=lambda: defaultdict(list))
    active_dynamics: GradualChangeInstruction | None = None
    active_tempo: GradualChangeInstruction | None = None
    pattern_dict: dict[str, list[Note]] = field(default_factory=dict)

    def create_default_goto(self, beat: Beat) -> GoTo:
        self.goto_dict[beat.full_id] = GoTo(from_beat=beat, to_beat_dict={DEFAULT: beat.next})
        return self.goto_dict[beat.full_id]

    def goto(self, beat: Beat, create_if_none: bool = True) -> GoTo:
        """Returns the GoTo object for the beat or a newly created default GoTo value"""
        goto = self.goto_dict.get(beat.full_id, None)
        if not goto and create_if_none:
            goto = self.create_default_goto(beat)
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

    def assign_tempo(self, beat: Beat, meta: TempoMeta) -> None:
        """Assigns a Dynamics object for the given beat"""
        tempo = GradualChangeInstruction(
            passes=meta.passes,
            iterations=meta.iterations,
            tot_beats=meta.beat_count,
            target_value=meta.value,
        )
        self.tempo_dict[beat.full_id].append(tempo)

    def assign_dynamics(self, beat: Beat, meta: DynamicsMeta) -> None:
        """Assigns a Dynamics item for the given beat, for each position in positions.
        Note that contrary to Tempo items, multiple Dynamics items can be assigned to the same beat.
        This is because each Dynamics item can apply to a different (set of) instrument(s)."""
        dynamics = GradualChangeInstruction(
            positions=meta.positions,
            passes=meta.passes,
            iterations=meta.iterations,
            tot_beats=meta.beat_count,
            target_value=meta.value,
        )
        self.dynamics_dict[beat.full_id].append(dynamics)

    def initialize_tempo_and_dynamics(self):
        default_dynamics = self.score.settings.midi.dynamics[self.score.settings.midi.default_dynamics]
        default_tempo = 60

        self.active_tempo = GradualChangeInstruction(tot_beats=0, target_value=default_tempo)
        self.active_tempo.initialize_status(default_tempo)

        self.active_dynamics = GradualChangeInstruction(tot_beats=0, target_value=default_dynamics)
        self.active_dynamics.initialize_status(default_dynamics)

    def update_tempo_and_dynamics_status(self) -> GradualChangeInstruction:
        matching_tempo = next(
            (
                d
                for d in self.tempo_dict[self.curr_beat.full_id]
                if d.matches(
                    self.curr_position, self.get_curr_pass(self.curr_beat), self.get_curr_iteration(self.curr_beat)
                )
            ),
            None,
        )
        if matching_tempo and matching_tempo != self.active_tempo:
            # New tempo instruction
            current_value = self.active_tempo.status.end_value
            self.active_tempo.clear_status()
            self.active_tempo = matching_tempo
            self.active_tempo.initialize_status(initial_value=current_value)
        self.active_tempo.next_step()

        matching_dynamics = next(
            (
                d
                for d in self.dynamics_dict[self.curr_beat.full_id]
                if d.matches(
                    self.curr_position, self.get_curr_pass(self.curr_beat), self.get_curr_iteration(self.curr_beat)
                )
            ),
            None,
        )
        if matching_dynamics and matching_dynamics != self.active_dynamics:
            # New dynamics instruction
            current_value = self.active_dynamics.status.end_value
            self.active_dynamics.clear_status()
            self.active_dynamics = matching_dynamics
            self.active_dynamics.initialize_status(initial_value=current_value)
        self.active_dynamics.next_step()

    def get_curr_pass(self, beat: Beat) -> int:
        return self.goto(beat).counter

    def get_curr_iteration(self, beat: Beat) -> int | None:
        if self.loop(beat):
            return self.loop(beat).counter
        return DEFAULT

    def reset_all(self, position: Position):
        """Resets all GoTo and Loop counters"""
        for goto in self.goto_dict.values():
            goto.reset_counter()
        for loop in self.loop_dict.values():
            loop.reset_counter()
        self.curr_position = position
        self.initialize_tempo_and_dynamics()

    def next_beat_in_flow(self) -> Beat:
        """Determines the next beat, based on flow information and the current status
        of the execution (specifically the pass sequence for the given beat).
        Args:
            beat (Beat): beat from which to determine the next beat to be executed
        Returns:
            Beat: _description_
        """
        next_beat = None
        if not self.curr_beat:
            # Start of execution. Assign dummy current beat
            self.curr_beat = Beat(id=-1, gongan_id=-1)
            next_beat = self.score.gongans[0].beats[0]
        else:
            if loop := self.loop(self.curr_beat):
                # Retrieve next beat from Loop item (returns None if there are no more iterations)
                if self.curr_beat is loop.from_beat:
                    # Start with next iteration
                    next_beat = loop.next_beat(self.curr_beat)

        # Retrieve next beat: note that goto contains default value for next beat
        if not next_beat:
            next_beat = self.goto(self.curr_beat).next_beat()
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
            # If the next beat is in a new gongan and is not the first beat of the gongan,
            #  update the pass counter of the preceding beats in the gongan. This could otherwise
            # cause confusion e.g. when setting tempo at the beginning of the gongan for a specific pass.
            if self.curr_beat.gongan_id != next_beat.gongan_id and next_beat.id > 1:
                prev_beat = next_beat.prev
                while prev_beat and prev_beat.gongan_id == next_beat.gongan_id:
                    self.goto(prev_beat).counter = self.goto(next_beat).counter
                    prev_beat = prev_beat.prev
            self.curr_beat = next_beat
        else:
            self.curr_beat = None

        if self.curr_beat:
            self.update_tempo_and_dynamics_status()
        return self.curr_beat

    def get_tempo_values(self) -> tuple[int, int]:
        """Returns the tempo for the given beat."""
        return (self.active_tempo.status.start_value, self.active_tempo.status.end_value)

    def get_dynamics_values(self) -> tuple[int, int]:
        """Returns the dynamics for the given beat and position."""
        return (self.active_dynamics.status.start_value, self.active_dynamics.status.end_value)
