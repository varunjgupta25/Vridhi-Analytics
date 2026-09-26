from __future__ import annotations

import csv
from pathlib import Path

from vridhi_sim.config import SimulationConfig
from vridhi_sim.entities import ClimateShock
from vridhi_sim.risk_engine import RiskEngine, RiskEngineConfig, build_learning_dataset
from vridhi_sim.simulator import MicroEconomySimulator


def _risk_dataset(tmp_path: Path) -> Path:
    output = tmp_path / "dataset"
    shocks = [
        ClimateShock(2025, 7, "413001", 0.72),
        ClimateShock(2025, 8, "413001", 0.81),
        ClimateShock(2025, 9, "413001", 0.64),
        ClimateShock(2025, 7, "431001", 0.34),
    ]
    MicroEconomySimulator(SimulationConfig(output_dir=output), shocks).run().export()
    return output


def test_training_rows_use_the_next_month_label(tmp_path: Path) -> None:
    dataset = _risk_dataset(tmp_path)
    rows = build_learning_dataset(dataset)
    with (dataset / "borrower_month_labels.csv").open(newline="", encoding="utf-8") as handle:
        labels = list(csv.DictReader(handle))
    expected = {
        (row["farmer_id"], row["month"]): int(row["synthetic_30dpd"])
        for row in labels
    }
    first = rows[0]
    year, month, _ = (int(part) for part in str(first["month"]).split("-"))
    next_month = f"{year + 1:04d}-01-01" if month == 12 else f"{year:04d}-{month + 1:02d}-01"
    assert first["target_30dpd_next_month"] == expected[(first["farmer_id"], next_month)]


def test_scores_are_bounded_explainable_and_never_auto_decisions(tmp_path: Path) -> None:
    rows = build_learning_dataset(_risk_dataset(tmp_path))
    engine = RiskEngine(RiskEngineConfig(relational_adjustment_enabled=True)).fit(rows)
    score = engine.score([rows[-1]])[0]
    assert 0.0 < score["risk_pd"] < 1.0
    assert abs(score["relational_delta"]) <= 0.03
    assert score["recommended_action"] == "manual_review_required"
    assert len(__import__("json").loads(score["reason_codes"])) == 3
