from abc import ABC, abstractmethod
from enum import Enum, auto


class StateID(Enum):
    INITIALIZE = auto()
    PR1 = auto()
    PR2 = auto()
    PR3 = auto()
    UNLOCKED = auto()


class State(ABC):
    """Abstract base class for all states."""

    def __init__(self):
        # No config here
        pass

    def on_enter(self):
        """Called when entering the state."""
        pass

    def on_exit(self):
        """Called when exiting the state."""
        pass

    @abstractmethod
    def next_state(self, input_data):
        """
        Must return the next StateID.
        """
        pass

    def __str__(self):
        return self.__class__.__name__


# ------------------------------------------
# Concrete states
# ------------------------------------------

class Initialize(State):
    def on_enter(self):
        print("[Initialize] System preparing...")

    def next_state(self, input_data):
        # If input is truthy -> go forward, else -> stay in Initialize
        if input_data:
            return StateID.PR1
        return StateID.INITIALIZE


class PR1(State):
    def on_enter(self):
        print("[PR1] Detecting first hand...")

    def next_state(self, input_data):
        if input_data:
            return StateID.PR2
        return StateID.INITIALIZE


class PR2(State):
    def on_enter(self):
        print("[PR2] Second stage...")

    def next_state(self, input_data):
        if input_data:
            return StateID.PR3
        return StateID.INITIALIZE


class PR3(State):
    def on_enter(self):
        print("[PR3] Third stage...")

    def next_state(self, input_data):
        if input_data:
            return StateID.UNLOCKED
        return StateID.INITIALIZE


class Unlocked(State):
    def on_enter(self):
        print("[Unlocked] Sequence recognized. System unlocked.")

    def next_state(self, input_data):
        # Always return to initial
        return StateID.INITIALIZE


# ------------------------------------------
# Factory
# ------------------------------------------

def StateFactory(state_id):
    """Create the proper State instance for the given StateID."""
    if state_id == StateID.INITIALIZE:
        return Initialize()
    if state_id == StateID.PR1:
        return PR1()
    if state_id == StateID.PR2:
        return PR2()
    if state_id == StateID.PR3:
        return PR3()
    if state_id == StateID.UNLOCKED:
        return Unlocked()

    raise ValueError("Invalid StateID: %s" % state_id)
