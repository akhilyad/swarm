"""Custom exceptions for the Hyrex platform."""


class SwarmError(Exception):
    """Base exception for all swarm errors."""


class ConfigError(SwarmError):
    """Raised when configuration is invalid or missing."""


class RegistryError(SwarmError):
    """Raised when a node lookup fails."""


class CommunicationError(SwarmError):
    """Raised on message bus failures."""


class LLMError(SwarmError):
    """Raised when an LLM call fails."""


class MemoryError(SwarmError):
    """Raised on vector store failures."""
