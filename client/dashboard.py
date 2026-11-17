"""Compatibility entry point for ``python -m client.dashboard``."""

from .edgedet.dashboard import main

if __name__ == "__main__":
    raise SystemExit(main())
