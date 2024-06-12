from django.core.cache import caches
from pydantic import BaseModel, field_validator


class Settings(BaseModel):
    """Settings class used to parse the settings from the Django settings file.

    :param BaseModel: Pydantic BaseModel
    :type BaseModel: BaseModel
    """

    cache: str | None = "default"
    timeout: int | None = None

    # TODO: add possibility to rename/hide age, x-cache headers (are other headers needed?)

    @field_validator("cache")
    @classmethod
    def validate_cache(cls, v: str) -> str:
        if v not in caches:
            raise ValueError(f"Cache `{v}` not found in Django settings.")

        return v

    @field_validator("timeout")
    @classmethod
    def validate_timeout(cls, v: int) -> int:
        if v < 1:
            raise ValueError("timeout must be >= 1.")

        return v
