from enum import Enum

from pydantic import BaseModel, field_validator

# TODO: how to implement a __str__ method for each header? this would allow to fill it in dynamically in _set_headers
# TODO: are there any other headers needed?


class XCacheHeader(str, Enum):
    hit = "HIT"
    miss = "MISS"


class Headers(BaseModel):
    age: int
    x_cache: XCacheHeader

    @field_validator("age")
    @classmethod
    def validate_age(cls, v: int) -> int:
        if v < 0:
            raise ValueError("age must be >= 0.")

        return v
