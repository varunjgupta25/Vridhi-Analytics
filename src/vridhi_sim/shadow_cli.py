"""Phase 9 CLI for running shadow-mode pilot evaluations."""

from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd

from .risk_engine import RiskEngine, build_learning_dataset
from .shadow_engine import ShadowPilotEngine


def main() -> None:
    parser = argparse.ArgumentParser(description="Run Vridhi Phase 9 Shadow-Mode Pilot Evaluation.")
    parser.add_argument("--scores", type=Path, default=Path("artifacts/risk/reference/research_scores.csv"))
    parser.add_argument("--dataset", type=Path, default=Path("data/generated/reference"))
    parser.add_argument("--artifact-dir", type=Path, default=Path("artifacts/risk/reference"),
                        help="Directory containing risk_engine.joblib (for real scoring-path latency measurement)")
    parser.add_argument("--output", type=Path, default=Path("artifacts/shadow/reference"))
    args = parser.parse_args()

    if not args.scores.exists():
        print(f"Error: Scores file does not exist at {args.scores.resolve()}")
        return

    scores_df = pd.read_csv(args.scores)
    labels_file = args.dataset / "borrower_month_labels.csv"
    labels_df = pd.read_csv(labels_file) if labels_file.exists() else None

    # Load trained engine and raw feature rows for real scoring-path latency measurement.
    # Falls back to None (latency reported as null) if artifacts are absent.
    risk_engine: RiskEngine | None = None
    sample_rows: list[dict] | None = None
    engine_file = args.artifact_dir / "risk_engine.joblib"
    if engine_file.exists() and args.dataset.exists():
        try:
            risk_engine = RiskEngine.load(args.artifact_dir)
            sample_rows = build_learning_dataset(args.dataset)
            print(f"Loaded risk engine from {engine_file} ({len(sample_rows)} rows for latency measurement)")
        except Exception as exc:
            print(f"Warning: could not load risk engine for latency measurement — {exc}")
            risk_engine = None
            sample_rows = None
    else:
        print(
            "Warning: risk_engine.joblib not found at "
            f"{engine_file.resolve()} — vridhi_avg_latency_ms will be null."
        )

    pilot = ShadowPilotEngine()
    report = pilot.evaluate_shadow_run(
        scores_df,
        labels_df,
        risk_engine=risk_engine,
        sample_rows=sample_rows,
    )

    args.output.mkdir(parents=True, exist_ok=True)
    report_file = args.output / "shadow_pilot_report.json"
    pilot.save_report(report, report_file)

    print(f"Shadow-mode pilot evaluation complete.")
    print(f"Report written to: {report_file.resolve()}")
    print(f"Disagreement rate: {report['disagreement_rate'] * 100:.2f}%")
    latency = report["latency_metrics"]["vridhi_avg_latency_ms"]
    if latency is not None:
        print(f"Vridhi avg latency (full scoring path): {latency:.4f} ms/row")
    else:
        print("Vridhi avg latency: not measured (risk_engine not available)")


if __name__ == "__main__":
    main()
