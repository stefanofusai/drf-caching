# drf-caching

A simple package to handle views caching in Django Rest Framework.

## Installation

```bash
pip install drf-caching
```

## Usage

To setup caching for a view, you can use the `@cache_view` decorator.

```python
from drf_caching.cache import cache_view

class MyView(APIView):
    @cache_view()
    def get(self, request):
        return Response({"message": "Hello, world!"})
```

You can pass the following keyword arguments to the `@cache_view` decorator:

- `timeout`: the cache timeout in seconds (can also be set on a global level using the `DRF_CACHING` settings)
- `keys`: an iterable of keys to use to buildd the cache key

```python
from drf_caching.cache import cache_view

class MyView(APIView):
    @cache_view(timeout=60, keys=[FooKey]) # TODO: add keys examples
    def get(self, request):
        return Response({"message": "Hello, world!"})
```

The following keys, available in the `drf_caching.keys` module, can be used:

- `FooKey`: simple key # TODO: add examples

If no keys are passed, the cache key will be built using the view name and the request's format.

The settings can be customized as such:

```python
DRF_CACHING = {
    "CACHE": "default",
    "HEADERS": ["age", "x-cache"],
    "TIMEOUT" 60,
}
```

The following settings are available:

- `CACHE`: the cache to use (defaults to `default`)
- `HEADERS`: a list of headers to include in the cache key (by default the following headers are included: `Age`, `ETag`, `Expires`, `X-Cache`)
- `TIMEOUT`: the default cache timeout in seconds (defaults to `60`)

## Acknowledgments

This project was strongly inspired by [drf-extensions](https://github.com/chibisov/drf-extensions).

## Contributing

Contributions are welcome! To get started, please refer to our [contribution guidelines](https://github.com/stefanofusai/scrapy-influxdb-exporter/blob/main/CONTRIBUTING.md).

## Issues

If you encounter any problems while using this package, please open a new issue [here](https://github.com/stefanofusai/scrapy-influxdb-exporter/issues).
