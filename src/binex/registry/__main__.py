"""Registry entry point — launch with `python -m binex.registry`."""

from __future__ import annotations

import os

import uvicorn


def main() -> None:
    host = os.environ.get("BINEX_REGISTRY_HOST", "0.0.0.0")
    port = int(os.environ.get("BINEX_REGISTRY_PORT", "8000"))
    uvicorn.run("binex.registry.app:app", host=host, port=port)


if __name__ == "__main__":
    main()
