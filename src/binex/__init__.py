"""Binex — debuggable runtime for A2A agents."""

__version__ = "0.8.0"


def __getattr__(name: str) -> object:
    # Lazy re-export so `from binex import observe` works without importing the
    # (litellm-heavy) observe module on every `import binex`.
    if name == "observe":
        from binex.observer import observe

        return observe
    raise AttributeError(f"module 'binex' has no attribute {name!r}")


__all__ = ["__version__", "observe"]
