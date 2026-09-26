"""Generate Phase 5 governance and monitoring reports."""

from __future__ import annotations

import argparse
import csv
from pathlib import Path

from .mlops import create_promotion_request, delayed_label_performance, drift_report, write_json
from .risk_engine import build_learning_dataset


def _scores(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def main() -> None:
    parser = argparse.ArgumentParser(description="Run Vridhi Phase 5 monitoring and governance tasks.")
    sub = parser.add_subparsers(dest="command", required=True)
    monitor = sub.add_parser("monitor")
    monitor.add_argument("--reference-dataset", type=Path, required=True)
    monitor.add_argument("--current-dataset", type=Path, required=True)
    monitor.add_argument("--scores", type=Path, required=True)
    monitor.add_argument("--output", type=Path, default=Path("artifacts/monitoring"))
    promote = sub.add_parser("request-promotion")
    promote.add_argument("--candidate", type=Path, required=True)
    promote.add_argument("--owner", required=True)
    promote.add_argument("--output", type=Path, default=Path("artifacts/governance/promotion_request.json"))
    args = parser.parse_args()
    if args.command == "monitor":
        reference, current = build_learning_dataset(args.reference_dataset), build_learning_dataset(args.current_dataset)
        drift = drift_report(reference, current)
        performance = delayed_label_performance(_scores(args.scores), current)
        write_json(args.output / "drift_report.json", drift)
        write_json(args.output / "delayed_label_performance.json", performance)
        print(f"Monitoring reports written to {args.output.resolve()} with drift status {drift['overall_status']}.")
    else:
        request = create_promotion_request(args.candidate, args.owner)
        write_json(args.output, request)
        print(f"Promotion request recorded at {args.output.resolve()}; no production model was changed.")


if __name__ == "__main__":
    main()
