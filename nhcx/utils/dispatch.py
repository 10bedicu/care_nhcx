"""
Helper for tracking the lifecycle of every outbound NHCX gateway request.

Every Claim / CoverageEligibilityRequest / Task that we POST to NHCX exposes
three tracking columns:

    dispatched_at    -- when we last handed it off to the gateway
    dispatch_error   -- last error text (empty string == no error)
    dispatch_status  -- machine-readable lifecycle state (DispatchStatusChoices)

The viewsets wrap each ``GatewayService.*`` call in ``dispatch(...)`` so all
three columns are updated in one place. Async state transitions that arrive
later via ProtocolResponse / ``/error/response`` callbacks or successful FHIR
response processing are handled by the callback handler and fhir.py directly.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from django.db.models import Model
from django.utils import timezone

from nhcx.models import DispatchStatusChoices
from nhcx.utils.exceptions import NHCXAPIException

# Postgres TEXT has no fixed cap, but bounding what we persist keeps obviously
# malformed payloads from blowing up the column / audit page.
_DISPATCH_ERROR_MAX = 8000


def _truncate(message: Any) -> str:
    return str(message or "")[:_DISPATCH_ERROR_MAX]


def dispatch[R](instance: Model, fn: Callable[..., R], *args, **kwargs) -> R:
    """
    Run ``fn(*args, **kwargs)`` (almost always a ``GatewayService.*`` call)
    and stamp dispatch metadata onto ``instance`` regardless of outcome.

    On success (gateway returned 202):
        * ``dispatched_at     = now()``
        * ``dispatch_error    = ""``
        * ``dispatch_status   = AWAITING``

    On ``NHCXAPIException`` (the gateway POST returned non-202):
        * ``dispatched_at     = now()``  -- we still attempted
        * ``dispatch_error    = exc.detail``
        * ``dispatch_status   = ERROR``
        * exception re-raised so the viewset surfaces it to the caller.

    On any other unexpected exception same persistence happens with a
    ``ClassName: message`` error text, then exception is re-raised.

    The save uses ``update_fields`` so we never clobber a concurrent edit
    on the same row (e.g. a callback writing ``status`` / ``meta``).
    """
    now = timezone.now()
    try:
        result = fn(*args, **kwargs)
    except NHCXAPIException as exc:
        _persist(
            instance,
            dispatched_at=now,
            dispatch_error=_truncate(exc.detail),
            dispatch_status=DispatchStatusChoices.ERROR,
        )
        raise
    except Exception as exc:
        _persist(
            instance,
            dispatched_at=now,
            dispatch_error=_truncate(f"{type(exc).__name__}: {exc}"),
            dispatch_status=DispatchStatusChoices.ERROR,
        )
        raise

    _persist(
        instance,
        dispatched_at=now,
        dispatch_error="",
        dispatch_status=DispatchStatusChoices.AWAITING,
    )
    return result


def _persist(
    instance: Model,
    *,
    dispatched_at,
    dispatch_error: str,
    dispatch_status: str,
) -> None:
    instance.dispatched_at = dispatched_at
    instance.dispatch_error = dispatch_error
    instance.dispatch_status = dispatch_status
    instance.save(
        update_fields=[
            "dispatched_at",
            "dispatch_error",
            "dispatch_status",
            "modified_date",
        ]
    )
