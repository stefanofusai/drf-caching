class CacheNotSupportedError(Exception):
    def __init__(self, cache: str) -> None:
        super().__init__(f"`{cache}` is not supported.")


class InvalidArgumentError(Exception):
    def __init__(self, error: str) -> None:
        super().__init__(f"Invalid argument: {error}")


class InvalidDataError(Exception):
    def __init__(self, data: dict) -> None:
        super().__init__(f"Invalid data: {data}")


class InvalidSettingsError(Exception):
    def __init__(self, error: str) -> None:
        super().__init__(f"`DRF_CACHING` settings are invalid: {error}")


class MissingSettingsError(Exception):
    def __init__(self) -> None:
        super().__init__("Please add `DRF_CACHING` to your Django settings file.")
