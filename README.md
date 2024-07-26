# drf-caching

A simple package to handle views caching in Django Rest Framework.

## Installation

```bash
pip install drf-caching
```

## Usage

To setup caching for a view, you can use the `@cache_view` decorator.

```python
from drf_caching import cache_view, GetQuerysetKey, PaginationKey, QueryParamsKey

class MyView(APIView):
    @cache_view(
        GetQuerysetKey(),
        PaginationKey(),
        QueryParamsKey("ordering", "search"),
        timeout=60,
    )
    def get(self, request):
        return Response({"message": "Hello, world!"})
```

You can pass multiple keys to the decorator, and the cache key will be built using all of them.
You can pass the following keyword arguments to the `@cache_view` decorator:

- `timeout`: the cache timeout in seconds (can also be set on a global level using the `DRF_CACHING` setting)

The following keys, available in the `drf_caching.keys` module, can be used:

- `GetObjectKey`: the cache key will be built using the view's get_object method
- `GetQuerylistKey`: the cache key will be built using the view's get_querylist method from [django-rest-multiple-models](https://github.com/MattBroach/DjangoRestMultipleModels)
- `GetQuerysetKey`: the cache key will be built using the view's get_queryset method
- `HeadersKey`: the cache key will be built using the request's headers
- `KwargsKey`: the cache key will be built using the request's kwargs
- `LookupFieldKey`: the cache key will be built using the view's kwarg matching the lookup field
- `PaginationKey`: the cache key will be built using the request's pagination parameters
- `QueryParamsKey`: the cache key will be built using the request's query parameters
- `UserKey`: the cache key will be built using the request's user

If no keys are passed, the cache key will be built using the view name and the request's format.

The settings can be customized as such:

```python
DRF_CACHING = {
    "CACHE": "default",
    "HEADERS": ["age", "x-cache"],
    "TIMEOUT": 60,
}
```

To disable caching for a specific view, or even globally, you can set `timeout` to `0`.

The following settings are available:

- `CACHE`: the cache to use (defaults to `default`)
- `HEADERS`: a list of lowercase headers to include in the cache key (by default the following headers are included: `age`, `cache-control`, `etag`, `expires`, `x-cache`)
- `TIMEOUT`: the default cache timeout in seconds

To create your own cache key, you can subclass the `BaseKey` and `BaseKeyWithFields` classes and implement the `_get_data` method.

```python
from drf_caching import BaseKey, BaseKeyWithFields

class CustomKey(BaseKey):
    def _get_data(self, view_instance, view_method, request, *args, **kwargs):
        return {
            "key": "value"
        }

class CustomKeyWithFields(BaseKeyWithFields):
    def _get_data(self, view_instance, view_method, request, *args, **kwargs):
        return {
            field: ...
            for field in self.fields
        }
```

## Acknowledgments

This project was strongly inspired by [drf-extensions](https://github.com/chibisov/drf-extensions).

## Contributing

Contributions are welcome! To get started, please refer to our [contribution guidelines](https://github.com/stefanofusai/drf-caching/blob/main/CONTRIBUTING.md).

## Issues

If you encounter any problems while using this package, please open a new issue [here](https://github.com/stefanofusai/drf-caching/issues).
