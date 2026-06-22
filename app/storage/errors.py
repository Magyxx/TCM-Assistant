from __future__ import annotations


class StorageError(RuntimeError):
    """Base storage error for P7 persistence."""


class StorageUnavailable(StorageError):
    """Raised when a configured storage backend cannot be used."""


class StorageRecordNotFound(StorageError):
    """Raised when an expected persisted record is missing."""
