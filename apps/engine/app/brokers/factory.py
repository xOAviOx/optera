"""Broker adapter factory — selects the active *data* broker from config.

`BROKER=upstox` (default) reads live positions via the OAuth access token;
`BROKER=mock` serves a synthetic demo book with no credentials. The Upstox
OAuth connect flow (M2) is separate and always uses UpstoxAdapter directly.
"""

from __future__ import annotations

from app.brokers.base import BrokerAdapter
from app.brokers.mock import MockBrokerAdapter
from app.brokers.upstox import UpstoxAdapter
from app.config import get_settings

_REGISTRY: dict[str, type[BrokerAdapter]] = {
    "upstox": UpstoxAdapter,
    "mock": MockBrokerAdapter,
}
# Adapters are stateless; cache one instance per resolved broker name.
_instances: dict[str, BrokerAdapter] = {}


def get_broker_adapter() -> BrokerAdapter:
    """The adapter for the configured broker (defaults to Upstox if unknown)."""
    name = (get_settings().broker or "upstox").lower()
    adapter_cls = _REGISTRY.get(name, UpstoxAdapter)
    if name not in _instances:
        _instances[name] = adapter_cls()
    return _instances[name]
