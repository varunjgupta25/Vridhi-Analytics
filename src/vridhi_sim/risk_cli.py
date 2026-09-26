"""Train and export the Phase 2 synthetic research risk engine.

Training-duration and peak-memory are measured with stdlib primitives only:
  - time.perf_counter()    → wall-clock training duration
  - tracemalloc            → Python-heap peak (excludes XGBoost native C allocations)
  - _process_rss_mb()      → process RSS (WorkingSetSize on Windows via ctypes,
                              ru_maxrss on POSIX via resource module)

Both memory figures are labelled by name; neither is silently substituted for
the other.  No new dependencies beyond the declared project requirements.
"""

from __future__ import annotations

import argparse
import platform
import sys
import time
import tracemalloc
from pathlib import Path
from typing import Any

from .risk_engine import RiskEngine, RiskEngineConfig, build_learning_dataset, write_scores
from .mlops import model_card, write_json


# ---------------------------------------------------------------------------
# Cross-platform process RSS helper (stdlib only)
# ---------------------------------------------------------------------------

def _process_rss_mb() -> tuple[float | None, str]:
    """Return current process RSS in MiB using stdlib-only APIs.

    Returns
    -------
    rss_mb : float or None
        Resident Set Size in mebibytes, or None if the platform is unsupported.
    source_note : str
        Human-readable description of which API was used and its caveats.
    """
    system = platform.system()

    if system == "Windows":
        # ctypes ships with CPython on Windows — no extra dependency.
        # PROCESS_MEMORY_COUNTERS_EX from psapi.dll gives WorkingSetSize,
        # which is the closest Windows equivalent to POSIX RSS.
        import ctypes
        import ctypes.wintypes

        class _PROCESS_MEMORY_COUNTERS_EX(ctypes.Structure):
            _fields_ = [
                ("cb", ctypes.wintypes.DWORD),
                ("PageFaultCount", ctypes.wintypes.DWORD),
                ("PeakWorkingSetSize", ctypes.c_size_t),
                ("WorkingSetSize", ctypes.c_size_t),
                ("QuotaPeakPagedPoolUsage", ctypes.c_size_t),
                ("QuotaPagedPoolUsage", ctypes.c_size_t),
                ("QuotaPeakNonPagedPoolUsage", ctypes.c_size_t),
                ("QuotaNonPagedPoolUsage", ctypes.c_size_t),
                ("PagefileUsage", ctypes.c_size_t),
                ("PeakPagefileUsage", ctypes.c_size_t),
                ("PrivateUsage", ctypes.c_size_t),
            ]

        try:
            counters = _PROCESS_MEMORY_COUNTERS_EX()
            counters.cb = ctypes.sizeof(counters)
            # GetCurrentProcess() returns the current-process pseudo-handle.
            # On Python 3.14 the return value of GetCurrentProcess() is not
            # automatically marshalled as a HANDLE; using the documented
            # constant value (-1 / 0xFFFFFFFF) avoids the marshalling issue.
            handle = ctypes.wintypes.HANDLE(-1)
            ok = ctypes.windll.psapi.GetProcessMemoryInfo(
                handle, ctypes.byref(counters), ctypes.sizeof(counters)
            )
            if ok:
                rss_mb = counters.WorkingSetSize / (1024 * 1024)
                note = (
                    "Windows WorkingSetSize via ctypes + psapi.GetProcessMemoryInfo. "
                    "Includes XGBoost native C heap (unlike tracemalloc). "
                    "WorkingSetSize is a snapshot, not a peak — read after fit() completes."
                )
                return round(rss_mb, 2), note
        except Exception:
            pass
        return None, "Windows: GetProcessMemoryInfo call failed; RSS not available."

    elif system in ("Linux", "Darwin"):
        # resource is a POSIX-only stdlib module.
        import resource  # type: ignore[import]
        usage = resource.getrusage(resource.RUSAGE_SELF)
        if system == "Darwin":
            # macOS returns ru_maxrss in bytes
            rss_mb = usage.ru_maxrss / (1024 * 1024)
        else:
            # Linux returns ru_maxrss in kilobytes
            rss_mb = usage.ru_maxrss / 1024
        note = (
            f"POSIX resource.getrusage(RUSAGE_SELF).ru_maxrss "
            f"({'bytes on macOS' if system == 'Darwin' else 'KiB on Linux'}). "
            "Peak RSS since process start — includes XGBoost native C heap."
        )
        return round(rss_mb, 2), note

    else:
        return None, f"Unsupported platform '{system}'; process RSS not measured."


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(description="Train Vridhi's synthetic research risk engine.")
    parser.add_argument("--dataset", type=Path, default=Path("data/generated/reference"))
    parser.add_argument("--output", type=Path, default=Path("artifacts/risk/reference"))
    parser.add_argument("--enable-relational-adjustment", action="store_true")
    parser.add_argument("--train-gnn-candidate", action="store_true",
                        help="Train a validation-gated temporal GraphSAGE research candidate")
    parser.add_argument("--mlflow-tracking-uri",
                        help="Optional MLflow tracking URI for this reviewed synthetic training run")
    args = parser.parse_args()

    rows = build_learning_dataset(args.dataset)

    # ── Measure training wall-clock time and Python-heap peak ──────────────
    tracemalloc.start()
    t0 = time.perf_counter()

    engine = RiskEngine(
        RiskEngineConfig(relational_adjustment_enabled=args.enable_relational_adjustment)
    ).fit(rows)

    train_wall_s = time.perf_counter() - t0
    _, python_heap_peak_bytes = tracemalloc.get_traced_memory()
    tracemalloc.stop()

    # ── Process-level RSS (includes XGBoost native C allocations) ──────────
    process_rss_mb, rss_note = _process_rss_mb()

    training_profile: dict[str, Any] = {
        "train_wall_clock_seconds": round(train_wall_s, 3),
        "python_heap_peak_mb": round(python_heap_peak_bytes / (1024 * 1024), 4),
        "python_heap_peak_note": (
            "tracemalloc.get_traced_memory() — Python object heap only. "
            "Does NOT include XGBoost's native C allocations. "
            "Almost certainly understates true process memory use."
        ),
        "process_rss_mb": process_rss_mb,
        "process_rss_note": rss_note,
        "training_rows": len(rows),
        "profiling_note": (
            "Wall-clock time measured with time.perf_counter(). "
            "Excludes dataset loading and artifact serialisation I/O. "
            "Both memory figures are included; see individual *_note fields "
            "for what each covers and its caveats."
        ),
    }

    output = engine.save(args.output, training_profile=training_profile)
    write_json(output / "model_card.json", model_card(engine, str(args.dataset), training_profile=training_profile))
    scores = engine.score(rows)
    write_scores(output / "research_scores.csv", scores)

    if args.train_gnn_candidate:
        from .gnn_research import TemporalGraphSAGECandidate

        candidate = TemporalGraphSAGECandidate().fit(args.dataset)
        candidate.save(output)
        print(f"Validation-gated GraphSAGE candidate: {candidate.metrics}")

    if args.mlflow_tracking_uri:
        from .mlflow_tracking import track_training

        print(f"MLflow run: {track_training(engine, output, args.mlflow_tracking_uri)}")

    print(f"Trained synthetic research engine using {len(rows)} point-in-time rows in {output.resolve()}")
    print(f"Evaluation: {engine.metrics}")
    print(f"Training profile: {training_profile}")


if __name__ == "__main__":
    main()
