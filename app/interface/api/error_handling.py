# app/interface/api/error_handling.py
from typing import Callable, TypeVar

from fastapi import HTTPException

from app.domain.shared.errors import DomainValidationError, NotFoundError
from app.domain.shared.state_machine import InvalidStateTransitionError

T = TypeVar("T")


def run(action: Callable[[], T]) -> T:
    try:
        return action()
    except NotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except InvalidStateTransitionError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except DomainValidationError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
