import pytest

from app.domain.shared.state_machine import InvalidStateTransitionError, StateMachineMixin


class TrafficLight(StateMachineMixin):
    TRANSITIONS = {
        "red": {"go": "green"},
        "green": {"caution": "yellow"},
        "yellow": {"stop": "red"},
    }

    def __init__(self) -> None:
        self.status = "red"


def test_legal_transition_changes_status():
    light = TrafficLight()

    light._transition("go")

    assert light.status == "green"


def test_illegal_transition_raises_and_leaves_status_unchanged():
    light = TrafficLight()

    with pytest.raises(InvalidStateTransitionError):
        light._transition("stop")

    assert light.status == "red"
