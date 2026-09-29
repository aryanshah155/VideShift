"""Engine selection: prefer PySpark when importable, else pandas fallback."""

from __future__ import annotations

import importlib.util

SPARK_IMPORT_ERROR: str | None = None

try:  # pragma: no cover - environment dependent
    importlib.util.find_spec("pyspark")
    import pyspark  # noqa: F401

    SPARK_AVAILABLE = True
except Exception as exc:  # noqa: BLE001
    SPARK_AVAILABLE = False
    SPARK_IMPORT_ERROR = f"{type(exc).__name__}: {exc}"


def engine_status() -> dict:
    """Report which engine will be used and why."""
    if SPARK_AVAILABLE:
        reason = (
            "PySpark is importable; runs will use distributed MLlib "
            "(VectorAssembler -> StandardScaler -> KMeans -> PCA)."
        )
        return {"engine": "spark", "spark_available": True, "reason": reason}
    reason = (
        "PySpark is not available in this Python environment "
        f"({SPARK_IMPORT_ERROR or 'not installed'}). "
        "Falling back to the single-node pandas/sklearn engine, which mirrors the "
        "Spark pipeline stage-for-stage (VectorAssembler+StandardScaler via numpy, "
        "KMeans with seed=42, PCA to 2 components)."
    )
    return {"engine": "pandas", "spark_available": False, "reason": reason}


def get_engine():
    """Return an instantiated engine based on availability."""
    if SPARK_AVAILABLE:
        from .spark_engine import SparkEngine

        return SparkEngine()
    from .pandas_engine import PandasEngine

    return PandasEngine()
