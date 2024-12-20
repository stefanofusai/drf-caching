import hashlib
import json
import time
from collections import defaultdict
from collections.abc import Callable
from datetime import UTC, datetime
from functools import wraps
from typing import Any, Literal

from bs4 import BeautifulSoup
from django.conf import settings as django_settings
from django.core.cache import BaseCache, caches
from django.core.cache.backends.db import DatabaseCache
from django.core.cache.backends.dummy import DummyCache
from django.core.cache.backends.filebased import FileBasedCache
from django.core.cache.backends.locmem import LocMemCache
from django.core.cache.backends.memcached import PyLibMCCache, PyMemcacheCache
from django.core.cache.backends.redis import RedisCache
from django.http.response import HttpResponse
from django_redis.cache import RedisCache as DjangoRedisCache
from pydantic import ValidationError
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from .exceptions import (
    CacheNotSupportedError,
    HeaderNotSupportedError,
    InvalidArgumentError,
    InvalidSettingsError,
    MissingSettingsError,
)
from .keys import BaseKey
from .sentinels import Sentinel
from .settings import Settings
from .utils import NotGiven


class CacheView:
    """CacheView class used to cache API responses."""

    def __init__(
        self, *keys: BaseKey, timeout: int | None | Sentinel = NotGiven
    ) -> None:
        """
        Create an instance of the CacheView class.

        :param keys: the keys used to generate the cache key.
        :type keys: BaseKey
        :param timeout: the cache timeout, defaults to NotGiven.
        :type timeout: int | None | Sentinel, optional
        :raises CacheNotSupportedError: if the specified cache is not supported.
        :raises HeaderNotSupportedError: if the age header is passed and the specified cache does not support it.
        :raises HeaderNotSupportedError: if the age header is passed and the specified cache does not support it.
        :raises InvalidArgumentError: if any key is not an instance of BaseKey.
        :raises InvalidArgumentError: if the timeout is not an integer.
        :raises InvalidArgumentError: if the timeout is less than 1.
        :raises InvalidArgumentError: if the timeout is neither defined in the settings nor passed as an argument.
        """
        self.settings = self._get_settings()
        self.cache = self._get_cache()
        self.headers = self._get_headers(timeout)
        self.keys = self._get_keys(keys)
        self.timeout = self._get_timeout(timeout)

    def __call__(self, func: Callable[..., Response]) -> Callable[..., Response]:
        """
        Wrap a view function or method to enable caching.

        :param func: The view function or method to be wrapped.
        :type func: Callable[..., Response]
        :return: The wrapped view function or method.
        :rtype: Callable[..., Response]
        """

        @wraps(func)
        def inner(
            view_instance: APIView, request: Request, *args: Any, **kwargs: Any
        ) -> Response:
            return self._get_response(view_instance, func, request, *args, **kwargs)

        return inner

    # Private methods

    def _get_age(self, key: str) -> int | None:
        age = {
            DatabaseCache: lambda: None,
            DjangoRedisCache: lambda: self.timeout - self.cache.ttl(key),
            DummyCache: lambda: None,
            FileBasedCache: lambda: None,
            LocMemCache: lambda: round(
                self.timeout
                - (
                    self.cache._expire_info.get(self.cache.make_key(key))  # noqa: SLF001
                    - time.time()
                )
            ),
            PyLibMCCache: lambda: None,
            PyMemcacheCache: lambda: None,
            RedisCache: lambda: None,
        }[type(self.cache)]()

        match age:
            case 0:
                return 1

            case self.timeout:
                return self.timeout - 1

            case _:
                return age

    def _get_cache(self) -> BaseCache:
        cache = caches[self.settings.CACHE]

        if not isinstance(
            cache,
            DatabaseCache
            | DjangoRedisCache
            | DummyCache
            | FileBasedCache
            | PyLibMCCache
            | PyMemcacheCache
            | RedisCache
            | LocMemCache,
        ):
            raise CacheNotSupportedError(cache)

        return cache

    def _get_expires(self, key: str) -> str | None:
        return {
            DatabaseCache: lambda: None,
            DjangoRedisCache: lambda: datetime.fromtimestamp(
                time.time() + self.cache.ttl(key), tz=UTC
            ).strftime("%a, %d %b %Y %H:%M:%S GMT"),
            DummyCache: lambda: None,
            FileBasedCache: lambda: None,
            LocMemCache: lambda: datetime.fromtimestamp(
                self.cache._expire_info.get(self.cache.make_key(key)),  # noqa: SLF001
                tz=UTC,
            ).strftime("%a, %d %b %Y %H:%M:%S GMT"),
            PyLibMCCache: lambda: None,
            PyMemcacheCache: lambda: None,
            RedisCache: lambda: None,
        }[type(self.cache)]()

    def _get_headers(
        self, timeout: int | None | Sentinel
    ) -> list[Literal["age", "cache-control", "etag", "expires", "x-cache"]]:
        if (
            isinstance(
                self.cache,
                DatabaseCache
                | DummyCache
                | FileBasedCache
                | PyLibMCCache
                | PyMemcacheCache
                | RedisCache,
            )
            and self.settings.HEADERS is not None
        ):
            if "age" in self.settings.HEADERS:
                raise HeaderNotSupportedError(
                    "age",  # noqa: EM101
                    reason=f"{self.cache.__class__.__name__} does not implement it",
                )

            if "expires" in self.settings.HEADERS:
                raise HeaderNotSupportedError(
                    "expires",  # noqa: EM101
                    reason=f"{self.cache.__class__.__name__} does not implement it",
                )

        if timeout is None or self.settings.TIMEOUT is None:
            if "age" in self.settings.HEADERS:
                raise HeaderNotSupportedError("age", reason="cache timeout is None")  # noqa: EM101

            if "cache-control" in self.settings.HEADERS:
                raise HeaderNotSupportedError(
                    "cache-control",  # noqa: EM101
                    reason="cache timeout is None",
                )

        return self.settings.HEADERS

    def _get_key(
        self,
        view_instance: APIView,
        view_method: Callable[..., Response],
        request: Request,
        *args: Any,
        **kwargs: Any,
    ) -> str:
        key_dict = {
            "view_id": f"{view_method.__module__}.{view_method.__qualname__}",
            "format": request.accepted_renderer.format,
            # Allows for multiple keys of the same type to be passed
            # without overwriting each other
            "keys": defaultdict(list),
        }

        for key in self.keys:
            key_dict["keys"][key.__class__.__name__].append(
                key.get_key(view_instance, view_method, request, *args, **kwargs)
            )

        return hashlib.md5(json.dumps(key_dict, sort_keys=True).encode()).hexdigest()  # noqa: S324

    def _get_keys(self, keys: tuple[BaseKey, ...]) -> tuple[BaseKey, ...]:
        for key in keys:
            if not isinstance(key, BaseKey):
                msg = "key must be an instance of BaseKey"
                raise InvalidArgumentError(msg)

        return keys

    def _get_response(
        self,
        view_instance: APIView,
        view_method: Callable[..., Response],
        request: Request,
        *args: Any,
        **kwargs: Any,
    ) -> HttpResponse | Response:
        key = self._get_key(view_instance, view_method, request, *args, **kwargs)
        response_quadruple = self.cache.get(key)

        if response_quadruple is None:
            response = self._get_response_from_view(
                key, request, view_instance, view_method, args, kwargs
            )

        else:
            response = self._get_response_from_cache(
                key,
                response_quadruple[0],
                response_quadruple[1],
                response_quadruple[2],
                response_quadruple[3],
            )

        return response

    def _get_response_from_cache(  # noqa: PLR0913, RUF100
        self,
        key: str,
        status: int,
        content: bytes,
        headers: dict[str, str],
        accepted_media_type: str,
    ) -> HttpResponse:
        if "age" in self.headers:
            age = self._get_age(key)

            if age is not None:
                headers["Age"] = age

        if "cache-control" in self.headers and "cache-control" not in headers:
            headers["Cache-Control"] = f"max-age={self.timeout}"

        if "etag" in self.headers and "etag" not in headers:
            headers["ETag"] = key

        if "expires" in self.headers and "expires" not in headers:
            expires = self._get_expires(key)

            if expires is not None:
                headers["Expires"] = expires

        if "x-cache" in self.headers and (
            "x-cache" not in headers or headers["x-cache"] == "MISS"
        ):
            headers["X-Cache"] = "HIT"

        if accepted_media_type == "text/html":
            html = BeautifulSoup(content, "lxml")
            span = html.new_tag("span", **{"class": "meta nocode"})
            span.append(html.find("span", class_="meta nocode").find("b"))
            span.append("\n")

            for header, value in sorted(headers.items(), key=lambda x: x[0]):
                tag = html.new_tag("b")
                tag.string = f"{header}:"
                span.append(tag)
                span.append(" ")

                tag = html.new_tag("span", **{"class": "lit"})
                tag.string = value
                span.append(tag)
                span.append("\n")

            span.append("\n")
            html.find("span", class_="meta nocode").replace_with(span)
            content = str(html)

        return HttpResponse(content, status=status, headers=headers)

    def _get_response_from_view(  # noqa: PLR0913, RUF100
        self,
        key: str,
        request: Request,
        view_instance: APIView,
        view_method: Callable[..., Response],
        args: Any,
        kwargs: Any,
    ) -> Response:
        response = view_instance.finalize_response(
            request,
            view_method(view_instance, request, *args, **kwargs),
            *args,
            **kwargs,
        )

        if response.status_code < 400:
            if "age" in self.headers:
                response.headers["Age"] = 0

            if "cache-control" in self.headers:
                response.headers["Cache-Control"] = f"max-age={self.timeout}"

            if "x-cache" in self.headers:
                response.headers["X-Cache"] = "MISS"

            response.render()
            self.cache.set(
                key,
                (
                    response.status_code,
                    response.content,
                    response.headers,
                    response.accepted_media_type,
                ),
                self.timeout,
            )

        else:
            response.render()

        return response

    def _get_settings(self) -> Settings:
        try:
            settings = django_settings.DRF_CACHING

        except AttributeError:
            raise MissingSettingsError from None

        if not isinstance(settings, dict):
            msg = "settings must be a dictionary"
            raise InvalidSettingsError(msg)

        try:
            return Settings(**settings)

        except ValidationError as e:
            raise InvalidSettingsError(e) from None

    def _get_timeout(self, timeout: int | None | Sentinel) -> int | None:
        if timeout is NotGiven and self.settings.TIMEOUT is NotGiven:
            msg = "timeout must be either defined in the settings or passed as an argument"
            raise InvalidArgumentError(msg)

        if (
            timeout is not None
            and timeout is not NotGiven
            and not isinstance(timeout, int)
        ):
            msg = "timeout must be either None or an integer"
            raise InvalidArgumentError(msg)

        if isinstance(timeout, int) and timeout < 0:
            msg = "timeout must be >= 0"
            raise InvalidArgumentError(msg)

        return self.settings.TIMEOUT if timeout is NotGiven else timeout


cache_view = CacheView
