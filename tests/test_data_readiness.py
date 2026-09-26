from __future__ import annotations

import csv
import shutil
from pathlib import Path

from vridhi_sim.data_readiness import synthetic_to_real_readiness, validate_synthetic_dataset


REFERENCE = Path("data/generated/reference")


def test_reference_dataset_is_valid_for_synthetic_research_only() -> None:
    report = validate_synthetic_dataset(REFERENCE)
    readiness = synthetic_to_real_readiness(report)
    assert report["overall_status"] == "PASS"
    assert report["temporal_alignment"]["status"] == "PASS"
    assert readiness["decision"] == "SYNTHETIC_RESEARCH_ONLY"
    assert readiness["real_borrower_scoring_allowed"] is False


def test_validator_rejects_outcome_leakage_in_feature_snapshot(tmp_path: Path) -> None:
    dataset = tmp_path / "dataset"
    shutil.copytree(REFERENCE, dataset)
    path = dataset / "node_month.csv"
    with path.open(newline="", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))
        fields = list(rows[0]) + ["synthetic_30dpd"]
    for row in rows:
        row["synthetic_30dpd"] = "0"
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)
    report = validate_synthetic_dataset(dataset)
    assert report["overall_status"] == "FAIL"
    assert any(issue["code"] == "outcome_leakage_column" for issue in report["issues"])
