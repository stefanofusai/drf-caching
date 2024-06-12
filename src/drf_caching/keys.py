from abc import ABC, abstractmethod
from collections.abc import Callable
from typing import Any

from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from .exceptions import InvalidArgumentError, InvalidDataError


class BaseKey(ABC):
    # Public methods

    def get_key(
        self,
        view_instance: APIView,
        view_method: Callable[..., Response],
        request: Request,
        *args: Any,
        **kwargs: Any,
    ) -> str:
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
    def __init__(self, *fields: str) -> None:
        for field in fields:
            if not isinstance(field, str):
                raise InvalidArgumentError(f"field must be a str, not {type(field)}.")

        self.fields = fields
