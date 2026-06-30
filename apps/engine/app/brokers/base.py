"""Broker adapter contract. Implementations normalize each broker into one shape.

v1 is READ-ONLY: positions/holdings/market-data only. No order placement methods exist
here on purpose — that keeps us out of execution liability.
"""
//
//
//
//
//
//
//
//
//
from __future__ import annotations

from abc import ABC, abstractmethod

from pydantic import BaseModel


class NormalizedPosition(BaseModel):
    """Broker-agnostic position shape consumed by the quant core."""

    instrument_token: str
    tradingsymbol: str
    name: str | None = None
    option_type: str | None = None  # CE / PE / None(=FUT/EQ)
    strike: float | None = None
    expiry: str | None = None
    quantity: int  # signed: long > 0, short < 0
    lot_size: int
    average_price: float
    last_price: float | None = None
    pnl: float | None = None


class BrokerAdapter(ABC):
    """All brokers implement this. Tokens are passed in already-decrypted by the caller."""

    broker_name: str
    # Real brokers need a decrypted access token; demo/mock brokers ignore it, so
    # callers can skip the token lookup entirely when this is False.
    requires_auth: bool = True

    @abstractmethod
    async def get_positions(self, access_token: str) -> list[NormalizedPosition]:
        """Live net positions for the day, normalized."""

    @abstractmethod
    async def get_holdings(self, access_token: str) -> list[NormalizedPosition]:
        """Longer-term holdings, normalized."""

    @abstractmethod
    async def get_margin(self, access_token: str) -> dict:
        """{'used': float, 'available': float, ...}."""

    @abstractmethod
    async def get_option_chain(self, analytics_token: str, symbol: str, expiry: str) -> dict:
        """Chain with IV + Greeks + OI per strike (provider-supplied)."""
