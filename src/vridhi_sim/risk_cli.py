"""Train and export the Phase 2 synthetic research risk engine.

Training-duration and peak-memory are measured with stdlib primitives
(time.perf_counter, tracemalloc) and recorded into risk_engine_metadata.json
and model_card.json.  No fabricated constants are used.
"""

from __future__ import annotations

import argparse
import time
import tracemalloc
from pathlib import Path

from .risk_engine import RiskEngine, RiskEngineConfig, build_learning_dataset, write_scores
from .mlops import model_card, write_json


def main() -> None:
    parser = argparse.ArgumentParser(description="Train Vridhi's synthetic research risk engine.")
    parser.add_argument("--dataset", type=Path, default=Path("data/generated/reference"))
    parser.add_argument("--output", type=Path, default=Path("artifacts/risk/reference"))
    parser.add_argument("--enable-relational-adjustment", action="store_true")
    parser.add_argument("--train-gnn-candidate", action="store_true", help="Train a validation-gated temporal GraphSAGE research candidate")
    parser.add_argument("--mlflow-tracking-uri", help="Optional MLflow tracking URI for this reviewed synthetic training run")
    args = parser.parse_args()

    rows = build_learning_dataset(args.dataset)

    # ── Measure training wall-clock time and peak heap allocation ──────────
    tracemalloc.start()
    t0 = time.perf_counter()

    engine = RiskEngine(RiskEngineConfig(relational_adjustment_enabled=args.enable_relational_adjustment)).fit(rows)

    train_wall_s = time.perf_counter() - t0
    _, peak_bytes = tracemalloc.get_traced_memory()
    tracemalloc.stop()

    training_profile = {
        "train_wall_clock_seconds": round(train_wall_s, 3),
        "peak_memory_mb": round(peak_bytes / (1024 * 1024), 2),
        "training_rows": len(rows),
        "profiling_note": (
            "Wall-clock time measured with time.perf_counter(); "
            "peak heap measured with tracemalloc.get_traced_memory(). "
            "Excludes dataset loading and artifact serialisation I/O."
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
