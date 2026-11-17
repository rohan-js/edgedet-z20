"""Compatibility entry point for ``python -m client.virtual_board``."""

from .edgedet.virtual_board import main

if __name__ == "__main__":
    raise SystemExit(main())
