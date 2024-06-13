from abc import ABC, abstractmethod
from collections.abc import Callable
from typing import Any

from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from .exceptions import InvalidArgumentError, InvalidDataError


class BaseKey(ABC):
    """Base class for generating cache keys based on provided parameters."""

    # Public methods

    def get_key(
        self,
        view_instance: APIView,
        view_method: Callable[..., Response],
        request: Request,
        *args: Any,
        **kwargs: Any,
    ) -> str:
        """Generate a cache key based on the provided parameters.

        :param view_instance: The instance of the view class.
        :type view_instance: APIView
        :param view_method: The method of the view class.
        :type view_method: Callable[..., Response]
        :param request: The request object.
        :type request: Request
        :return: The generated cache key.
        :rtype: str
        """
        return "&".join(
            [
                f"{k}={v}"
                for k, v in self._get_data_aux(
                    view_instance, view_method, request, *args, **kwargs
                ).items()
            ]
        )

    # Private methods

    @abstractmethod
    def _get_data(
        self,
        view_instance: APIView,
        view_method: Callable[..., Response],
        request: Request,
        *args: Any,
        **kwargs: Any,
    ) -> dict[str, str]: ...

    def _get_data_aux(
        self,
        view_instance: APIView,
        view_method: Callable[..., Response],
        request: Request,
        *args: Any,
        **kwargs: Any,
    ) -> dict[str, str]:
        data = self._get_data(
            view_instance, view_method, request, *args, **kwargs
        ).items()

        for k, v in data:
            if not isinstance(k, str) or not isinstance(v, str):
                raise InvalidDataError(data)

        return data


class BaseKeyWithFields(BaseKey):
    """A base key class with fields.

    This class represents a key with multiple fields. It is a subclass of `BaseKey`.

    :param fields: Variable number of string arguments representing the fields of the key.
    :raises InvalidArgumentError: If any of the fields is not a string.
    """  # noqa: E501

    def __init__(self, *fields: str) -> None:
        """Initialize a Key instance with the given fields.

        :param fields: Variable number of string arguments representing the fields of the key.
        :raises InvalidArgumentError: If any of the fields is not a string.
        """  # noqa: E501
        for field in fields:
            if not isinstance(field, str):
                raise InvalidArgumentError(f"field must be a str, not {type(field)}.")

        self.fields = fields


# TODO: implement
