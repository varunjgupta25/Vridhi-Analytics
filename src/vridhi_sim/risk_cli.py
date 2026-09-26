"""Train and export the Phase 2 synthetic research risk engine."""

from __future__ import annotations

import argparse
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
    engine = RiskEngine(RiskEngineConfig(relational_adjustment_enabled=args.enable_relational_adjustment)).fit(rows)
    output = engine.save(args.output)
    write_json(output / "model_card.json", model_card(engine, str(args.dataset)))
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


if __name__ == "__main__":
    main()
