class InvalidStateTransitionError(Exception):
    def __init__(self, current_state, action: str) -> None:
        super().__init__(f"cannot perform '{action}' from state '{current_state}'")
        self.current_state = current_state
        self.action = action


class StateMachineMixin:
    """
    Mix into any entity with a `status` attribute. Subclasses declare a
    class-level `TRANSITIONS` dict shaped {current_status: {action: next_status}}
    and call self._transition(action) inside each action method.
    """

    TRANSITIONS: dict = {}

    def _transition(self, action: str) -> None:
        allowed = self.TRANSITIONS.get(self.status, {})
        if action not in allowed:
            raise InvalidStateTransitionError(self.status, action)
        self.status = allowed[action]
