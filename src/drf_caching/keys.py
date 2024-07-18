from abc import ABC, abstractmethod
from collections.abc import Callable
from typing import Any

from django.db.models import Manager
from rest_framework.pagination import (
    CursorPagination,
    LimitOffsetPagination,
    PageNumberPagination,
)
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from .exceptions import (
    InvalidArgumentError,
    InvalidDataError,
    UnsupportedPaginatorError,
)

# Base classes


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
    ) -> dict[str, Any]: ...

    def _get_data_aux(
        self,
        view_instance: APIView,
        view_method: Callable[..., Response],
        request: Request,
        *args: Any,
        **kwargs: Any,
    ) -> dict[str, Any]:
        data = self._get_data(view_instance, view_method, request, *args, **kwargs)

        for k in data:
            if not isinstance(k, str):
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


# Key classes


class GetObjectKey(BaseKey):
    """A key class for generating cache keys based on the views' object."""

    def _get_data(
        self,
        view_instance: APIView,
        view_method: Callable[..., Response],
        request: Request,
        *args: Any,
        **kwargs: Any,
    ) -> dict[str, Any]:
        data = {}
        obj = view_instance.get_object()

        for field in obj._meta.get_fields():  # noqa: SLF001
            _attr = getattr(obj, field.name)
            data[field.name] = (
                _attr.all().values_list() if isinstance(_attr, Manager) else _attr
            )

        return data


class GetQuerylistKey(BaseKey):
    """A key class for generating cache keys based on the views' querylist from the django-rest-multiple-models package."""  # noqa: E501

    def _get_data(
        self,
        view_instance: APIView,
        view_method: Callable[..., Response],
        request: Request,
        *args: Any,
        **kwargs: Any,
    ) -> dict[str, Any]:
        return {
            "querylist": [
                querylist["queryset"].values_list()
                for querylist in view_instance.filter_queryset(
                    view_instance.get_querylist()
                )
            ]
        }


class GetQuerysetKey(BaseKey):
    """A key class for generating cache keys based on the views' queryset."""

    def _get_data(
        self,
        view_instance: APIView,
        view_method: Callable[..., Response],
        request: Request,
        *args: Any,
        **kwargs: Any,
    ) -> dict[str, Any]:
        return {
            "queryset": view_instance.filter_queryset(
                view_instance.get_queryset()
            ).values_list()
        }


class HeadersKey(BaseKeyWithFields):
    """A key class for generating cache keys based on the request headers."""

    def _get_data(
        self,
        view_instance: APIView,
        view_method: Callable[..., Response],
        request: Request,
        *args: Any,
        **kwargs: Any,
    ) -> dict[str, Any]:
        return {field: request.headers.get(field) for field in self.fields}


class KwargsKey(BaseKeyWithFields):
    """A key class for generating cache keys based on the request keyword arguments."""

    def _get_data(
        self,
        view_instance: APIView,
        view_method: Callable[..., Response],
        request: Request,
        *args: Any,
        **kwargs: Any,
    ) -> dict[str, Any]:
        return {field: kwargs.get(field) for field in self.fields}


class LookupFieldKey(BaseKey):
    """A key class for generating cache keys based on the views' kwarg matching the lookup field."""  # noqa: E501

    def _get_data(
        self,
        view_instance: APIView,
        view_method: Callable[..., Response],
        request: Request,
        *args: Any,
        **kwargs: Any,
    ) -> dict[str, Any]:
        return {"lookup_field": kwargs.get(view_instance.lookup_field)}


class PaginationKey(BaseKey):
    """A key class for generating cache keys based on the request pagination parameters."""  # noqa: E501

    def _get_data(
        self,
        view_instance: APIView,
        view_method: Callable[..., Response],
        request: Request,
        *args: Any,
        **kwargs: Any,
    ) -> dict[str, Any]:
        paginator = view_instance.paginator

        if isinstance(paginator, PageNumberPagination):
            data = {
                "page": request.query_params.get(paginator.page_query_param),
                "page_size": request.query_params.get(paginator.page_size_query_param),
            }

        elif isinstance(paginator, LimitOffsetPagination):
            data = {
                "limit": request.query_params.get(paginator.limit_query_param),
                "offset": request.query_params.get(paginator.offset_query_param),
            }

        elif isinstance(paginator, CursorPagination):
            data = {
                "cursor": request.query_params.get(paginator.cursor_query_param),
                "page_size": request.query_params.get(paginator.page_size_query_param),
            }

        else:
            raise UnsupportedPaginatorError(paginator)

        return data


class QueryParamsKey(BaseKeyWithFields):
    """A key class for generating cache keys based on the request query parameters."""

    def _get_data(
        self,
        view_instance: APIView,
        view_method: Callable[..., Response],
        request: Request,
        *args: Any,
        **kwargs: Any,
    ) -> dict[str, Any]:
        return {field: request.query_params.getlist(field) for field in self.fields}


class UserKey(BaseKey):
    """A key class for generating cache keys based on the request user."""

    def _get_data(
        self,
        view_instance: APIView,
        view_method: Callable[..., Response],
        request: Request,
        *args: Any,
        **kwargs: Any,
    ) -> dict[str, Any]:
        return {"user": request.user.id}
