"""Controller backend abstraction (spec section 47).

The steering engine never talks to a specific backend directly - only to
this interface - so backends are swappable.
"""
from __future__ import annotations

from abc import ABC, abstractmethod


class VirtualController(ABC):
    @abstractmethod
    def connect(self) -> bool:
        ...

    @abstractmethod
    def disconnect(self) -> None:
        ...

    @property
    @abstractmethod
    def is_connected(self) -> bool:
        ...

    @abstractmethod
    def set_steering(self, value: float) -> None:
        """value in [-1.0, 1.0]."""

    def set_throttle(self, value: float) -> None:
        """value in [0.0, 1.0]. Default no-op for backends that don't support it."""

    def set_brake(self, value: float) -> None:
        """value in [0.0, 1.0]. Default no-op."""

    def set_button(self, button: str, pressed: bool) -> None:
        """Default no-op for backends without buttons."""

    @abstractmethod
    def center(self) -> None:
        """Set steering to 0 and throttle/brake to 0."""

    @abstractmethod
    def emergency_stop(self) -> None:
        """Immediately zero everything and release all buttons."""
