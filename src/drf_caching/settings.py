from typing import Literal

from django.core.cache import caches
from pydantic import BaseModel, field_validator

from .sentinels import Sentinel
from .utils import NotGiven


class Settings(BaseModel):
    """
    Settings class used to parse the settings from the Django settings file.

    :param BaseModel: Pydantic BaseModel.
    :type BaseModel: BaseModel
    """

    CACHE: str | None = "default"
    HEADERS: list[Literal["age", "cache-control", "etag", "expires", "x-cache"]] = [
        "age",
        "cache-control",
        "etag",
        "expires",
        "x-cache",
    ]
    TIMEOUT: int | None | Sentinel = NotGiven

    @field_validator("CACHE")
    @classmethod
    def validate_cache(cls, v: str) -> str:
        """
        Validate the CACHE field.

        :param v: The CACHE field.
        :type v: str
        :raises ValueError: if CACHE is not found in Django settings.
        :return: The CACHE field.
        :rtype: str
        """
        if v not in caches:
            msg = f"Cache `{v}` not found in Django settings."
            raise ValueError(msg)

        return v

    @field_validator("TIMEOUT")
    @classmethod
    def validate_timeout(cls, v: int | None | Sentinel) -> int | None | Sentinel:
        """
        Validate the TIMEOUT field.

        :param v: The TIMEOUT field.
        :type v: int | None | Sentinel
        :raises ValueError: if TIMEOUT is less than 0.
        :return: The TIMEOUT field.
        :rtype: int | None | Sentinel
        """
        if isinstance(v, int) and v < 0:
            msg = "timeout must be >= 0."
            raise ValueError(msg)

        return v
