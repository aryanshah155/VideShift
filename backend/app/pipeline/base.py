"""Pipeline engine contract shared by the Spark and pandas implementations."""

from __future__ import annotations

from typing import Any, Callable, Protocol

from ..schemas import Benchmark, RunConfig


class PipelineEngine(Protocol):
    """A pipeline engine produces a results payload from the raw dataset."""

    name: str

    def run(
        self,
        df: Any,
        config: RunConfig,
        progress: Callable[[str], None] | None = None,
    ) -> dict[str, Any]:
        """Execute all stages; return the standard results dict."""
        ...  # pragma: no cover


def stage_progress(
    name: str,
    progress: Callable[[str], None] | None,
) -> Callable[[str], None]:
    """Helper that prefixes messages with the stage name."""
    if progress is None:
        return lambda msg: None

    def cb(msg: str) -> None:
        progress(f"[{name}] {msg}")

    return cb


__all__ = ["PipelineEngine", "stage_progress", "Benchmark"]
