class DomainValidationError(Exception):
    """Raised when an operation violates a business rule (not a state-machine rule)."""


class NotFoundError(Exception):
    """Raised when a requested aggregate does not exist."""
