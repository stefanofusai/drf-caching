from datetime import datetime
from enum import Enum

from pydantic import BaseModel, field_validator


class XCacheHeader(str, Enum):
    """XCacheHeader class used to define the X-Cache header values."""

    hit = "HIT"
    miss = "MISS"


class Headers(BaseModel):
    """Headers class used to parse the headers from the Django settings file.

    :param BaseModel: Pydantic BaseModel.
    :type BaseModel: BaseModel
    :raises ValueError: if age is less than 0.
    :return: Headers object.
    :rtype: Headers
    """

    age: int | None
    cache_control: str
    etag: str | None = None
    expires: datetime | None = None
    x_cache: XCacheHeader

    @field_validator("age")
    @classmethod
    def validate_age(cls, v: int) -> int:
        """Validate the age field.

        :param v: The age field.
        :type v: int
        :raises ValueError: if age is less than 0.
        :return: The age field.
        :rtype: int
        """
        if v < 0:
            raise ValueError("age must be >= 0.")

        return v

    @staticmethod
    def normalize(header) -> str:
        """Normalize a header string by converting it to lowercase and replacing hyphens with underscores.

        :param header: The header string to normalize.
        :type header: str
        :return: The normalized header string.
        :rtype: str
        """  # noqa: E501
        return header.lower().replace("-", "_")
