from __future__ import annotations

import csv
from pathlib import Path

import pytest

from vridhi_sim.config import RegionConfig, SimulationConfig
from vridhi_sim.entities import ClimateShock
from vridhi_sim.simulator import MicroEconomySimulator


def _config(tmp_path: Path) -> SimulationConfig:
    return SimulationConfig(
        months=4,
        farmers_per_region=6,
        retailers_per_region=1,
        wholesalers_per_region=1,
        seed=9,
        output_dir=tmp_path / "output",
        regions=(RegionConfig("413001", "Solapur", "soybean"),),
    )


def test_drought_reduces_farmer_crop_income_through_transactions(tmp_path: Path) -> None:
    config = _config(tmp_path)
    baseline = MicroEconomySimulator(config).run()
    drought = MicroEconomySimulator(
        config,
        [ClimateShock(2025, 3, "413001", 0.9), ClimateShock(2025, 4, "413001", 0.9)],
    ).run()

    def crop_income(simulation: MicroEconomySimulator) -> float:
        return sum(
            float(edge["amount_inr"])
            for edge in simulation.edges
            if edge["transaction_type"] == "crop_sale" and edge["pincode"] == "413001"
        )

    assert crop_income(drought) < crop_income(baseline)


def test_all_exported_cash_balances_are_non_negative_and_outputs_exist(tmp_path: Path) -> None:
    simulation = MicroEconomySimulator(_config(tmp_path)).run()
    assert all(agent.cash_balance >= 0 for agent in simulation.agents.values())
    destination = simulation.export()
    expected = {"nodes.csv", "edges.csv", "node_month.csv", "borrower_month_labels.csv", "scenario_summary.json"}
    assert expected.issubset({path.name for path in destination.iterdir()})
    with (destination / "edges.csv").open(newline="", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))
    assert rows
    assert {row["channel"] for row in rows} == {"upi"}


def test_climate_adapter_rejects_out_of_range_severity(tmp_path: Path) -> None:
    source = tmp_path / "invalid_shock.csv"
    source.write_text("year,month,pincode,drought_severity\n2025,7,413001,1.2\n", encoding="utf-8")
    with pytest.raises(ValueError, match="within"):
        MicroEconomySimulator.load_climate_shocks(source)
