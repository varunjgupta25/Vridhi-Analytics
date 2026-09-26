"""Run Phase 6 synthetic-data admission checks."""

from __future__ import annotations

import argparse
from pathlib import Path

from .data_readiness import synthetic_to_real_readiness, validate_synthetic_dataset, write_json


def main() -> None:
    parser = argparse.ArgumentParser(description="Validate Vridhi synthetic research data before risk-model work.")
    parser.add_argument("--dataset", type=Path, required=True)
    parser.add_argument("--output", type=Path, default=Path("artifacts/validation"))
    args = parser.parse_args()
    validation = validate_synthetic_dataset(args.dataset)
    readiness = synthetic_to_real_readiness(validation)
    write_json(args.output / "quality_report.json", validation)
    write_json(args.output / "data_readiness_report.json", readiness)
    print(f"Data quality: {validation['overall_status']}; admission decision: {readiness['decision']}.")
    print(f"Reports written to {args.output.resolve()}.")
    if validation["overall_status"] != "PASS":
        raise SystemExit(2)


if __name__ == "__main__":
    main()
