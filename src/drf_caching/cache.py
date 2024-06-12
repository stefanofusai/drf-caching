import hashlib
import json
import time
from collections import defaultdict
from collections.abc import Callable, Iterable
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
    InvalidArgumentError,
    InvalidSettingsError,
    MissingSettingsError,
)
from .headers import Headers, XCacheHeader
from .keys import BaseKey
from .settings import Settings


class CacheView:
    def __init__(
        self, timeout: int | None = None, keys: Iterable[BaseKey] | None = None
    ) -> None:
        self.settings = self._get_settings()

        cache = caches[self.settings.cache]

        if not isinstance(
            cache,
            PyMemcacheCache
            | PyLibMCCache
            | RedisCache
            | DatabaseCache
            | FileBasedCache
            | LocMemCache
            | DummyCache,
        ):
            raise CacheNotSupportedError(cache.__class__.__name__)

        self.cache = cache

        if timeout is None and self.settings.timeout is None:
            raise InvalidArgumentError(
                "timeout must be either defined in the settings or passed as an argument."  # noqa: E501
            )

        if timeout is not None and not isinstance(timeout, int):
            raise InvalidArgumentError("timeout must be an integer.")

        if timeout is not None and timeout < 1:
            raise InvalidArgumentError("timeout must be >= 1.")

        self.timeout = self.settings.timeout if timeout is None else timeout

        if keys is None:
            keys = []

        else:
            if not isinstance(keys, Iterable):
                raise InvalidArgumentError("keys must be an iterable.")

            for key in keys:
                if not isinstance(key, BaseKey):
                    raise InvalidArgumentError("keys must be an iterable of BaseKey.")

        self.keys = keys

    def __call__(self, func: Callable[..., Response]) -> Callable[..., Response]:
        @wraps(func)
        def inner(
            view_instance: APIView, request: Request, *args: Any, **kwargs: Any
        ) -> Response:
            return self._get_response(view_instance, func, request, *args, **kwargs)

        return inner

    # Private methods

    def _get_age(self, key: str) -> int:
        return {
            DjangoRedisCache: lambda: self.timeout - self.cache.ttl(key),
            LocMemCache: lambda: round(
                self.timeout
                - (
                    self.cache._expire_info.get(self.cache.make_key(key))  # noqa: SLF001
                    - time.time()
                )
            ),
            PyLibMCCache: lambda: self.timeout - self.cache.ttl(key),  # TODO: implement
            PyMemcacheCache: lambda: self.timeout
            - self.cache.ttl(key),  # TODO: implement
            RedisCache: lambda: self.timeout - self.cache.ttl(key),  # TODO: implement
            DatabaseCache: lambda: self.timeout
            - self.cache.ttl(key),  # TODO: implement
            FileBasedCache: lambda: self.timeout
            - self.cache.ttl(key),  # TODO: implement
            LocMemCache: lambda: self.timeout - self.cache.ttl(key),  # TODO: implement
            DummyCache: lambda: self.timeout - self.cache.ttl(key),  # TODO: implement
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
                self.cache.set(key, response, self.timeout)  # TODO: will pickling work?

            else:
                response.render()

        else:
            self._set_headers(
                response, Headers(age=self._get_age(key), x_cache=XCacheHeader.hit)
            )

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

        except ValidationError:
            raise InvalidSettingsError(
                "generic error"  # TODO: format error message from pydantic
            ) from None

    def _set_headers(self, response: Response, *, headers: Headers) -> None:
        # TODO: add possibility to customize which headers are returned
        response.headers["Age"] = headers.age
        response.headers["X-Cache"] = headers.x_cache.value

        if headers.x_cache == XCacheHeader.hit:
            response.content = (
                response.content.decode()
                .replace(
                    '<b>Age:</b> <span class="lit">0</span>',
                    f'<b>Age:</b> <span class="lit">{headers.age}</span>',
                    1,
                )
                .replace(
                    '<b>X-Cache:</b> <span class="lit">MISS</span>',
                    '<b>X-Cache:</b> <span class="lit">HIT</span>',
                    1,
                )
                .encode()
            )


cache_view = CacheView
