"""Stable provider-side radio errors without backend exception exposure."""


class RadioOperationError(RuntimeError):
    """A selected radio operation failed with a safe public description."""


class RadioTimeoutError(RadioOperationError):
    """An injected radio operation exceeded its caller-managed deadline."""
