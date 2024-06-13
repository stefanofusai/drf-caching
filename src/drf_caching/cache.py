import hashlib
import json
import re
import time
from collections import defaultdict
from collections.abc import Callable, Iterable
from datetime import UTC, datetime
from functools import wraps
from typing import Any

from django.conf import settings as django_settings
from django.core.cache import caches
from django.core.cache.backends.db import DatabaseCache
from django.core.cache.backends.dummy import DummyCache
from django.core.cache.backends.filebased import FileBasedCache
from django.core.cache.backends.locmem import LocMemCache
from django.core.cache.backends.memcached import PyLibMCCache, PyMemcacheCache
from django.core.cache.backends.redis import RedisCache
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
from .headers import Headers, XCacheHeader
from .keys import BaseKey
from .settings import Settings


class CacheView:
    """CacheView class used to cache API responses."""

    def __init__(
        self, *, timeout: int | None = None, keys: Iterable[BaseKey] | None = None
    ) -> None:
        """Create an instance of the CacheView class.

        :param timeout: the cache timeout, defaults to None.
        :type timeout: int | None, optional
        :param keys: the cache keys to use, defaults to None.
        :type keys: Iterable[BaseKey] | None, optional
        :raises CacheNotSupportedError: if the specified cache is not supported.
        :raises HeaderNotSupportedError: if the age header is passed and the specified cache does not support it.
        :raises HeaderNotSupportedError: if the age header is passed and the specified cache does not support it.
        :raises InvalidArgumentError: if the timeout is not an integer.
        :raises InvalidArgumentError: if the timeout is less than 1.
        :raises InvalidArgumentError: if the keys are not an iterable.
        :raises InvalidArgumentError: if the keys are not an iterable of BaseKey.
        :raises InvalidArgumentError: if the timeout is neither defined in the settings nor passed as an argument.
        """  # noqa: E501
        self.settings = self._get_settings()
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

        self.cache = cache

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
                raise HeaderNotSupportedError(self.cache, "Age")

            if "expires" in self.settings.HEADERS:
                raise HeaderNotSupportedError(self.cache, "Expires")

        self.headers = (
            Headers.model_fields
            if self.settings.HEADERS is None
            else [Headers.normalize(header) for header in self.settings.HEADERS]
        )

        if timeout is None and self.settings.TIMEOUT is None:
            raise InvalidArgumentError(
                "timeout must be either defined in the settings or passed as an argument."  # noqa: E501
            )

        if timeout is not None and not isinstance(timeout, int):
            raise InvalidArgumentError("timeout must be an integer.")

        if timeout is not None and timeout < 1:
            raise InvalidArgumentError("timeout must be >= 1.")

        self.timeout = self.settings.TIMEOUT if timeout is None else timeout

        if keys is None:
            self.keys = []

        else:
            if not isinstance(keys, Iterable):
                raise InvalidArgumentError("keys must be an iterable.")

            for key in keys:
                if not isinstance(key, BaseKey):
                    raise InvalidArgumentError("keys must be an iterable of BaseKey.")

            self.keys = keys

    def __call__(self, func: Callable[..., Response]) -> Callable[..., Response]:
        """Wrap a view function or method to enable caching.

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
            DatabaseCache: None,
            DjangoRedisCache: lambda: self.timeout - self.cache.ttl(key),
            DummyCache: lambda: None,
            FileBasedCache: None,
            LocMemCache: lambda: round(
                self.timeout
                - (
                    self.cache._expire_info.get(self.cache.make_key(key))  # noqa: SLF001
                    - time.time()
                )
            ),
            PyLibMCCache: None,
            PyMemcacheCache: None,
            RedisCache: lambda: None,
        }[type(self.cache)]()

        match age:
            case None:
                return None

            case 0:
                return 1

            case self.timeout:
                return self.timeout - 1

            case _:
                return age

    def _get_expires(self, key: str) -> datetime | None:
        return {
            DatabaseCache: None,
            DjangoRedisCache: lambda: datetime.fromtimestamp(
                time.time() + self.cache.ttl(key), tz=UTC
            ),
            DummyCache: lambda: None,
            FileBasedCache: None,
            LocMemCache: lambda: self.cache._expire_info.get(self.cache.make_key(key)),  # noqa: SLF001
            PyLibMCCache: None,
            PyMemcacheCache: None,
            RedisCache: lambda: None,
        }[type(self.cache)]()

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
            # withouth overwriting each other
            "keys": defaultdict(dict),
        }

        for key in self.keys:
            key_dict["keys"][key.__class__.__name__].update(
                key.get_key(view_instance, view_method, request, *args, **kwargs)
            )

        return hashlib.md5(json.dumps(key_dict, sort_keys=True).encode()).hexdigest()  # noqa: S324

    def _get_response(
        self,
        view_instance: APIView,
        view_method: Callable[..., Response],
        request: Request,
        *args: Any,
        **kwargs: Any,
    ) -> Response:
        key = self._get_key(view_instance, view_method, request, *args, **kwargs)
        response = self.cache.get(key)

        if response is None:
            response = view_instance.finalize_response(
                request,
                view_method(view_instance, request, *args, **kwargs),
                *args,
                **kwargs,
            )

            if response.status_code < 400:  # noqa: PLR2004
                self._set_headers(response, Headers(age=0, x_cache=XCacheHeader.miss))
                response.render()
                self.cache.set(key, response, self.timeout)

            else:
                response.render()

        else:
            self._set_headers(
                response,
                Headers(
                    age=self._get_age(key),
                    etag=key,
                    expires=self._get_expires(key),
                    x_cache=XCacheHeader.hit,
                ),
            )

            content = response.content.decode()

            for header, value in response.headers.items():
                if Headers.normalize(header) not in self.headers:
                    continue

                content = re.sub(
                    f'<b>{header}:</b> <span class="lit">.*?</span>',
                    f'<b>{header}:</b> <span class="lit">{value}</span>',
                    content,
                    count=1,
                )

                # TODO: it should also add new headers!
                # <span class="meta nocode">
                #     <b>HTTP 200 OK</b>
                #     <b>Age:</b> <span class="lit">0</span>
                #     <b>Allow:</b> <span class="lit">GET, HEAD, OPTIONS</span>
                #     <b>Content-Type:</b> <span class="lit">application/json</span>
                #     <b>Vary:</b> <span class="lit">Accept</span>
                #     <b>X-Cache:</b> <span class="lit">MISS</span>
                # </span>

            response.content = content.encode()

        return response

    def _get_settings(self) -> Settings:
        try:
            settings = django_settings.DRF_CACHING

        except AttributeError:
            raise MissingSettingsError from None

        if not isinstance(settings, dict):
            raise InvalidSettingsError("settings must be a dictionary.")

        try:
            return Settings(**settings)

        except ValidationError as e:
            raise InvalidSettingsError(e) from None

    def _set_headers(self, response: Response, headers: Headers) -> None:
        if "age" in self.headers and headers.age is not None:
            response.headers["Age"] = headers.age

        if headers.x_cache == XCacheHeader.hit:
            if "etag" in self.headers:
                response.headers["ETag"] = headers.etag

            if "expires" in self.headers and headers.expires is not None:
                response.headers["Expires"] = headers.expires.strftime(
                    "%a, %d %b %Y %H:%M:%S GMT"
                )

        if "x_cache" in self.headers:
            response.headers["X-Cache"] = headers.x_cache.value


cache_view = CacheView

# TODO: support calling the decorator without ()
