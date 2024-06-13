from django.core.cache import caches
from pydantic import BaseModel, field_validator

from .headers import Headers


class Settings(BaseModel):
    """Settings class used to parse the settings from the Django settings file.

    :param BaseModel: Pydantic BaseModel.
    :type BaseModel: BaseModel
    """

    CACHE: str | None = "default"
    HEADERS: list[str] | None = None
    TIMEOUT: int | None = None

    @field_validator("CACHE")
    @classmethod
    def validate_cache(cls, v: str) -> str:
        """Validate the CACHE field.

        :param v: The CACHE field.
        :type v: str
        :raises ValueError: if CACHE is not found in Django settings.
        :return: The CACHE field.
        :rtype: str
        """
        if v not in caches:
            raise ValueError(f"Cache `{v}` not found in Django settings.")

        return v

    @field_validator("HEADERS")
    @classmethod
    def validate_headers(cls, v: list[str] | None) -> list[str] | None:
        """Validate the HEADERS field.

        :param v: The HEADERS field.
        :type v: Iterable[str] | None
        :raises ValueError: if header is not supported.
        :return: The HEADERS field.
        :rtype: Iterable[str] | None
        """
        if v is None:
            return v

        for header in v:
            if Headers.normalize(header) not in Headers.model_fields:
                raise ValueError(f"Header `{header}` is not supported.")

        return v

    @field_validator("TIMEOUT")
    @classmethod
    def validate_timeout(cls, v: int) -> int:
        """Validate the TIMEOUT field.

        :param v: The TIMEOUT field.
        :type v: int
        :raises ValueError: if TIMEOUT is less than 1.
        :return: The TIMEOUT field.
        :rtype: int
        """
        if v < 1:
            raise ValueError("timeout must be >= 1.")

        return v
