"""Entry point for running the Living World simulation as a module.

Running ``python -m game`` now mirrors the behaviour of executing
``python -m game.main`` and will start the HTTP server on port 5000
while the simulation runs in the background.
"""

from . import main


def main_entrypoint() -> None:
    """Launch the simulation server using the existing main module."""

    main.run_server()


if __name__ == "__main__":  # pragma: no cover - convenience entrypoint
    main_entrypoint()
