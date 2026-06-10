"""
Base Publisher — Abstract interface for platform connectors.

All platform publishers implement this interface, allowing the
Publish Agent to call them uniformly through the ToolRegistry.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any


@dataclass
class PublishResult:
    """Result of a single publish attempt."""
    platform: str
    success: bool
    url: str | None = None
    error: str | None = None
    retry_count: int = 0


class BasePublisher(ABC):
    """Abstract base class for platform publishers."""

    def __init__(self, config: dict[str, Any] | None = None):
        self.config = config or {}
        self.name: str = "base"

    @abstractmethod
    def publish(self, title: str, content: str, tags: list[str] | None = None) -> PublishResult:
        """Publish an article to the platform."""
        ...

    @abstractmethod
    def validate_config(self) -> bool:
        """Check if the publisher configuration is valid."""
        ...

    def get_metadata(self) -> dict[str, Any]:
        """Return publisher metadata for agent discovery."""
        return {
            "name": self.name,
            "configured": self.validate_config(),
            "supports_tags": True,
            "supports_draft": True,
        }
