from __future__ import annotations

from vridhi_sim.config import SimulationConfig
from vridhi_sim.entities import ClimateShock
from vridhi_sim.gnn_research import GNNResearchConfig, TemporalGraphSAGECandidate
from vridhi_sim.simulator import MicroEconomySimulator


def test_graphsage_candidate_is_explicitly_research_only(tmp_path) -> None:
    dataset = tmp_path / "dataset"
    shocks = [ClimateShock(2025, 7, "413001", 0.72), ClimateShock(2025, 8, "413001", 0.81)]
    MicroEconomySimulator(SimulationConfig(output_dir=dataset), shocks).run().export()
    candidate = TemporalGraphSAGECandidate(GNNResearchConfig(epochs=2)).fit(dataset)
    assert candidate.metrics["candidate_only"] is True
    candidate.save(tmp_path / "artifacts")
    assert (tmp_path / "artifacts" / "graphsage_candidate_metrics.json").exists()
