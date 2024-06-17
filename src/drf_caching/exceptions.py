from typing import Any

from django.core.cache.backends.base import BaseCache
from pydantic import ValidationError


class CacheNotSupportedError(Exception):
    """Raised when the specified cache is not supported."""

    def __init__(self, cache: BaseCache) -> None:  # noqa: D107
        super().__init__(f"`{cache.__class__.__name__}` is not supported.")


class HeaderNotSupportedError(Exception):
    """Raised when the specified header is not supported."""

    def __init__(self, cache: BaseCache, header: str) -> None:  # noqa: D107
        super().__init__(
            f"`{cache.__class__.__name__}` does not support the `{header}` header."
        )


class InvalidArgumentError(Exception):
    """Raised when an invalid argument is passed."""

    def __init__(self, error: str) -> None:  # noqa: D107
        super().__init__(f"Invalid argument: {error}")


class InvalidDataError(Exception):
    """Raised when invalid data is passed to the key."""

    def __init__(self, data: dict) -> None:  # noqa: D107
        super().__init__(f"Data must be a dictionary with string keys, not {data}.")


class InvalidSettingsError(Exception):
    """Raised when the settings are invalid."""

    def __init__(self, error: ValidationError) -> None:  # noqa: D107
        super().__init__(f"`DRF_CACHING` settings are invalid: {error}")


class MissingSettingsError(Exception):
    """Raised when the settings are missing."""

    def __init__(self) -> None:  # noqa: D107
        super().__init__("Please add `DRF_CACHING` to your Django settings file.")


class UnsupportedPaginatorError(Exception):
    """Raised when the specified paginator is not supported."""

    def __init__(self, paginator: Any) -> None:  # noqa: D107
        super().__init__(f"`{paginator}` is not supported.")
