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
    """Keeps track of the current beat's start and end values of a gradual change (see below)"""

    beat_seq: int = 0  # current beat sequence (1..tot_beats)
    tot_beats: int = 0  # total number of beats involved in the gradual change.
    initial_value: int = 0  # value at the start of the gradual change.
    start_value: int = 0  # value at the start of the beat.
    end_value: int = 0  # (incremented) value at the end of the beat
    completed: bool = False  # Indicates whether the last change step has been executed.


class GradualChange(BaseModel):
    """Generic class that describes the gradual change of a musical expression value (tempo, dynamics) over multiple beats.
    Each instance of this class corresponds with a TEMPO or DYNAMICS metadata item.
    With a value of zero for tot_beats this class acts as an immediate (non-gradual) tempo or dynamics change."""

    positions: list[Position] = Field(default_factory=list)  # positions for which the instruction applies.
    passes: list[int] = Field(default_factory=list)
    iterations: list[int] = Field(default_factory=list)
    tot_beats: int = 0  # total number of beats involved in the gradual change.
    #                     If 0, the to_value should take effect immediately.
    from_value: int | None = None  # The initial value. If None, the 'current' value in the execution flow
    #                                is used as initial value.
    to_value: int = 0  # The final value of the gradual change.
    status: GradualChangeStatus | None = None  # Current status of the change

    def matches(self, position: Position, pass_nr: int, iteration_nr: int):
        """Returns True if the combination of arguments matches this GradualChange's fields.
        If a function argument is None, the matching field should be an empty list."""
        return (
            (position in self.positions or (position is None and not self.positions))
            and (pass_nr in self.passes or (pass_nr is None and not self.passes))
            and (iteration_nr in self.iterations or (iteration_nr is None and not self.iterations))
        )

    def clear_status(self):
        self.status = None

    def initialize_status(self, initial_value):
        """Initializes the gradual change. Initial value is the current value in the score's flow. If the GradualChange
        has a from_value!=None, it will overrule the current value. If tot_beats is 0, both start_value and end_value
        will be set to the GradualChange's to_value. In the latter case, from_value should be None or equal to to_value.
        """
        self.status = GradualChangeStatus(
            tot_beats=self.tot_beats,
            initial_value=(
                self.from_value if self.from_value else self.to_value if self.tot_beats == 0 else initial_value
            ),
            start_value=None,
            end_value=None,
        )

    def next_step(self) -> None:
        """Sets the status to the next step in the gradual change."""
        if self.status.completed:
            return
        self.status.beat_seq += 1
        if self.status.beat_seq > self.tot_beats:
            # Passed the end of the sequence: set both start and end values to the GradualChange's final value.
            # The value is now fixed for future beats.
            self.status.start_value = self.status.end_value = self.to_value
            self.status.completed = True
        elif self.status.beat_seq == self.tot_beats:
            # Last beat of the sequence: set the start value to the previous beat's end value, set end value to
            # the GradualChange's final value.
            self.status.start_value = self.status.initial_value if self.status.beat_seq == 1 else self.status.end_value
            self.status.end_value = self.to_value
        else:
            # Set the start value to the previous beat's end value and add one step increment for the end value.
            self.status.start_value = self.status.initial_value if self.status.beat_seq == 1 else self.status.end_value
            self.status.end_value = self.status.start_value + int(
                (self.to_value - self.status.start_value) / (self.tot_beats - self.status.beat_seq + 1)
            )


BeatID = str
GonganID = int


@dataclass
class ExecutionManager:
    """Takes care of the execution or 'performance' of a score. This consists of applying musical expression
    (dynamics, tempo) and flow (GOTO, LOOP and SEQUENCE).
    dynamics_dict and tempo_dict link GradualChange instances with the first beat
    of the change sequence.
    `active_tempo` and `active_dynamics` keep track of the currently active tempo and dynamics GradualChange instances.
    After the end of an active gradual change has been reached while processing the score's flow, it will remain active
    with its 'to_value' as the current value until a new GradualChange instruction is encountered.


    Returns:
        _type_: _description_
    """

    class MusicalExpressionType(StrEnum):
        TEMPO = "TEMPO"
        DYNAMICS = "DYNAMICS"

    score: Score
    curr_beat: Beat = None
    curr_position: Position = None
    goto_dict: dict[BeatID, GoTo] = field(default_factory=dict)
    loop_dict: dict[GonganID, Loop] = field(default_factory=dict)
    dynamics_dict: dict[BeatID, list[GradualChange]] = field(default_factory=lambda: defaultdict(list))
    tempo_dict: dict[BeatID, list[GradualChange]] = field(default_factory=lambda: defaultdict(list))
    active_dynamics: GradualChange | None = None
    active_tempo: GradualChange | None = None
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
        tempo = GradualChange(
            passes=meta.passes,
            iterations=meta.iterations,
            tot_beats=meta.beat_count,
            from_value=meta.from_value,
            to_value=meta.to_value,
        )
        self.tempo_dict[beat.full_id].append(tempo)

    def assign_dynamics(self, beat: Beat, meta: DynamicsMeta) -> None:
        """Assigns a Dynamics item for the given beat, for each position in positions."""
        dynamics = GradualChange(
            positions=meta.positions,
            passes=meta.passes,
            iterations=meta.iterations,
            tot_beats=meta.beat_count,
            from_value=meta.from_value,
            to_value=meta.to_value,
        )
        self.dynamics_dict[beat.full_id].append(dynamics)

    def initialize_gradual_change(self, initial_value: int) -> GradualChange:
        """Creates an initial active musical expression for the score's execution, with the given initial value."""
        gradual_change = GradualChange(tot_beats=0, from_value=initial_value, to_value=initial_value)
        gradual_change.status = GradualChangeStatus(end_value=initial_value)
        return gradual_change

    def update_gradual_change_status(self, change_type: MusicalExpressionType) -> None:
        """Updates the status values for the given musical expression type"""
        # Check if a new GradualChange is effective for the current beat, pass and loop.
        matching_value = None
        gradual_change_list = self.tempo_dict if change_type is self.MusicalExpressionType.TEMPO else self.dynamics_dict
        for pos_, pass_, iter_ in (
            (po, pa, it)
            for po in (self.curr_position, None)
            for pa in (self.get_curr_pass(self.curr_beat), None)
            for it in (self.get_curr_iteration(self.curr_beat), None)
        ):
            matching_value = next(
                (d for d in gradual_change_list[self.curr_beat.full_id] if d.matches(pos_, pass_, iter_)),
                None,
            )
            if matching_value:
                break

        # Determine the current active GradualChange
        active_change = self.active_tempo if change_type is self.MusicalExpressionType.TEMPO else self.active_dynamics
        if matching_value and matching_value != active_change:
            # New tempo or dynamics applies.
            # Copy the current tempo or dynamics value to initialize the new GradualChange.
            current_value = active_change.status.end_value
            active_change.clear_status()
            # Set the new GradualChange as the active one.
            active_change = matching_value
            active_change.initialize_status(initial_value=current_value)
        active_change.next_step()
        if change_type is self.MusicalExpressionType.TEMPO:
            self.active_tempo = active_change
        else:
            self.active_dynamics = active_change

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
        self.active_tempo = self.initialize_gradual_change(self.score.settings.midi.default_tempo)
        self.active_dynamics = self.initialize_gradual_change(
            self.score.settings.midi.dynamics[self.score.settings.midi.default_dynamics]
        )

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
            self.update_gradual_change_status(self.MusicalExpressionType.TEMPO)
            self.update_gradual_change_status(self.MusicalExpressionType.DYNAMICS)
        return self.curr_beat

    def get_tempo_values(self) -> tuple[int, int]:
        """Returns the tempo for the given beat."""
        return (self.active_tempo.status.start_value, self.active_tempo.status.end_value)

    def get_dynamics_values(self) -> tuple[int, int]:
        """Returns the dynamics for the given beat and position."""
        return (self.active_dynamics.status.start_value, self.active_dynamics.status.end_value)
