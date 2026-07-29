"""Infrastructure composition root for worker concurrency."""

from __future__ import annotations

from collections.abc import Callable

from fabricassist.application.limits import ConcurrencyGate
from fabricassist.infrastructure.concurrency.noop import NoOpConcurrencyGateAdapter
from fabricassist.infrastructure.concurrency.valkey import ValkeyConcurrencyGateAdapter
from fabricassist.settings import ConcurrencyGateBackend, Settings

ConcurrencyGateBuilder = Callable[[Settings], ConcurrencyGate]


def _valkey(settings: Settings) -> ConcurrencyGate:
    return ValkeyConcurrencyGateAdapter(
        url=settings.valkey_url,
        global_limit=settings.worker_global_concurrency,
        tenant_limit=settings.worker_tenant_concurrency,
        lease_seconds=settings.worker_concurrency_lease_seconds,
    )


def _noop(_settings: Settings) -> ConcurrencyGate:
    return NoOpConcurrencyGateAdapter()


CONCURRENCY_GATE_ADAPTERS: dict[ConcurrencyGateBackend, ConcurrencyGateBuilder] = {
    ConcurrencyGateBackend.VALKEY: _valkey,
    ConcurrencyGateBackend.NOOP: _noop,
}


def create_concurrency_gate(settings: Settings) -> ConcurrencyGate:
    """Select one registered worker-concurrency strategy."""
    try:
        builder = CONCURRENCY_GATE_ADAPTERS[settings.concurrency_gate_backend]
    except KeyError as error:  # pragma: no cover
        raise ValueError(
            f"Unsupported concurrency-gate backend: {settings.concurrency_gate_backend}"
        ) from error
    return builder(settings)
