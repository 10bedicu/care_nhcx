"""
Helper for tracking the lifecycle of every outbound NHCX gateway request.

Every Claim / CoverageEligibilityRequest / Task that we POST to NHCX exposes
two columns:

    dispatched_at   -- when we last handed it off to the gateway
    dispatch_error  -- last error text (empty string == success)

The viewsets wrap each ``GatewayService.*`` call in ``dispatch(...)`` so the
columns are updated in one place. Async errors that arrive later via
ProtocolResponse / ``/error/response`` callbacks are stamped onto the same
columns by ``_attach_error_to_anchor`` in the callback handler.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from django.db.models import Model
from django.utils import timezone

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

    On success:
        * ``dispatched_at = now()``
        * ``dispatch_error = ""``

    On ``NHCXAPIException`` (the gateway POST returned non-202, or the
    handshake/JWE encrypt failed):
        * ``dispatched_at = now()``  -- we still attempted dispatch
        * ``dispatch_error = exc.detail``
        * exception re-raised so the viewset surfaces it to the caller.

    On any other unexpected error the same persistence happens with a
    ``ClassName: message`` representation, then the exception is re-raised.

    The save uses ``update_fields`` so we never clobber a concurrent edit
    on the same row (e.g. a callback writing ``status`` / ``meta``).
    """
    now = timezone.now()
    try:
        result = fn(*args, **kwargs)
    except NHCXAPIException as exc:
        _persist(instance, dispatched_at=now, dispatch_error=_truncate(exc.detail))
        raise
    except Exception as exc:
        _persist(
            instance,
            dispatched_at=now,
            dispatch_error=_truncate(f"{type(exc).__name__}: {exc}"),
        )
        raise

    _persist(instance, dispatched_at=now, dispatch_error="")
    return result


def _persist(instance: Model, *, dispatched_at, dispatch_error: str) -> None:
    instance.dispatched_at = dispatched_at
    instance.dispatch_error = dispatch_error
    instance.save(update_fields=["dispatched_at", "dispatch_error", "modified_date"])
