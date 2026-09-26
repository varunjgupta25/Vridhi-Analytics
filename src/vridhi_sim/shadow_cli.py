"""Phase 9 CLI for running shadow-mode pilot evaluations."""

from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd

from .shadow_engine import ShadowPilotEngine


def main() -> None:
    parser = argparse.ArgumentParser(description="Run Vridhi Phase 9 Shadow-Mode Pilot Evaluation.")
    parser.add_argument("--scores", type=Path, default=Path("artifacts/risk/reference/research_scores.csv"))
    parser.add_argument("--dataset", type=Path, default=Path("data/generated/reference"))
    parser.add_argument("--output", type=Path, default=Path("artifacts/shadow/reference"))
    args = parser.parse_args()

    if not args.scores.exists():
        print(f"Error: Scores file does not exist at {args.scores.resolve()}")
        return

    scores_df = pd.read_csv(args.scores)
    labels_file = args.dataset / "borrower_month_labels.csv"
    labels_df = pd.read_csv(labels_file) if labels_file.exists() else None

    engine = ShadowPilotEngine()
    report = engine.evaluate_shadow_run(scores_df, labels_df)

    args.output.mkdir(parents=True, exist_ok=True)
    report_file = args.output / "shadow_pilot_report.json"
    engine.save_report(report, report_file)

    print(f"Shadow-mode pilot evaluation complete.")
    print(f"Report written to: {report_file.resolve()}")
    print(f"Disagreement rate: {report['disagreement_rate'] * 100:.2f}%")


if __name__ == "__main__":
    main()
