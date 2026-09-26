"""Validation-gated temporal GraphSAGE research candidate.

This module is intentionally separate from the deployed risk score. It is a
research comparison against XGBoost and must demonstrate incremental value on
real, consented, out-of-time data before it can influence any decision.
"""

from __future__ import annotations

import csv
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np
import torch
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import average_precision_score, brier_score_loss, roc_auc_score
from torch import nn

from .risk_engine import _subtract_months


@dataclass(frozen=True)
class GNNResearchConfig:
    hidden_dim: int = 16
    epochs: int = 80
    learning_rate: float = 0.01
    random_state: int = 42


class _GraphSAGE(nn.Module):
    def __init__(self, inputs: int, hidden: int):
        super().__init__()
        self.self_1, self.neighbour_1 = nn.Linear(inputs, hidden), nn.Linear(inputs, hidden)
        self.self_2, self.neighbour_2 = nn.Linear(hidden, 1), nn.Linear(hidden, 1)

    def forward(self, features: torch.Tensor, adjacency: torch.Tensor) -> torch.Tensor:
        hidden = torch.relu(self.self_1(features) + self.neighbour_1(adjacency @ features))
        return (self.self_2(hidden) + self.neighbour_2(adjacency @ hidden)).squeeze(-1)


class TemporalGraphSAGECandidate:
    """Small dependency-free GraphSAGE candidate with strict historical edges."""

    def __init__(self, config: GNNResearchConfig = GNNResearchConfig()):
        self.config = config
        self.model: _GraphSAGE | None = None
        self.calibrator: LogisticRegression | None = None
        self.metrics: dict[str, float | str | int] = {}

    @staticmethod
    def _read(path: Path) -> list[dict[str, str]]:
        with path.open(newline="", encoding="utf-8") as handle:
            return list(csv.DictReader(handle))

    def _samples(self, dataset_dir: Path) -> tuple[list[tuple[str, torch.Tensor, torch.Tensor, torch.Tensor]], list[str]]:
        nodes = self._read(dataset_dir / "nodes.csv")
        snapshots = self._read(dataset_dir / "node_month.csv")
        labels = self._read(dataset_dir / "borrower_month_labels.csv")
        edges = self._read(dataset_dir / "edges.csv")
        entity_ids = [node["entity_id"] for node in nodes]
        node_index = {entity: index for index, entity in enumerate(entity_ids)}
        type_index = {"farmer": 0, "kirana": 1, "wholesaler": 2, "utility_company": 3, "synthetic_lender": 4}
        node_types = [type_index.get(node["entity_type"], 5) for node in nodes]
        states = {(row["month"], row["entity_id"]): row for row in snapshots}
        labels_by_month: dict[str, dict[str, float]] = {}
        by_farmer: dict[str, list[dict[str, str]]] = {}
        for label in labels:
            by_farmer.setdefault(label["farmer_id"], []).append(label)
        for farmer_id, sequence in by_farmer.items():
            sequence.sort(key=lambda record: record["month"])
            for current, next_record in zip(sequence, sequence[1:]):
                labels_by_month.setdefault(current["month"], {})[farmer_id] = float(next_record["synthetic_30dpd"])
        samples: list[tuple[str, torch.Tensor, torch.Tensor, torch.Tensor]] = []
        for month in sorted(labels_by_month):
            feature_rows: list[list[float]] = []
            for entity, node_type in zip(entity_ids, node_types):
                state = states.get((month, entity), {})
                values = [
                    float(state.get("cash_balance", 0.0)) / 1_000_000.0,
                    float(state.get("income_inr", 0.0)) / 100_000.0,
                    float(state.get("expense_inr", 0.0)) / 100_000.0,
                    float(state.get("net_cash_flow_inr", 0.0)) / 100_000.0,
                    float(state.get("drought_severity", 0.0)),
                ]
                values.extend(1.0 if node_type == category else 0.0 for category in range(6))
                feature_rows.append(values)
            adjacency = np.eye(len(entity_ids), dtype=np.float32)
            window_start = _subtract_months(month, 3)
            for edge in edges:
                if window_start <= edge["timestamp"][:10] < month:
                    source, target = node_index[edge["source_id"]], node_index[edge["target_id"]]
                    adjacency[source, target] = adjacency[target, source] = 1.0
            degree = adjacency.sum(axis=1, keepdims=True)
            adjacency /= np.sqrt(degree * degree.T)
            labels_tensor = torch.full((len(entity_ids),), -1.0)
            for farmer_id, label in labels_by_month[month].items():
                labels_tensor[node_index[farmer_id]] = label
            samples.append((month, torch.tensor(feature_rows, dtype=torch.float32), torch.tensor(adjacency), labels_tensor))
        return samples, entity_ids

    def fit(self, dataset_dir: Path) -> "TemporalGraphSAGECandidate":
        torch.manual_seed(self.config.random_state)
        samples, _ = self._samples(dataset_dir)
        months = [sample[0] for sample in samples]
        train_end, calibration_end = int(len(months) * 0.60), int(len(months) * 0.80)
        train, calibration, test = samples[:train_end], samples[train_end:calibration_end], samples[calibration_end:]
        self.model = _GraphSAGE(train[0][1].shape[1], self.config.hidden_dim)
        train_labels = torch.cat([sample[3][sample[3] >= 0] for sample in train])
        negative = int((train_labels == 0).sum().item())
        positive = int((train_labels == 1).sum().item())
        pos_weight = torch.tensor([negative / max(positive, 1)], dtype=torch.float32)
        loss_function, optimiser = nn.BCEWithLogitsLoss(pos_weight=pos_weight), torch.optim.Adam(self.model.parameters(), lr=self.config.learning_rate)
        for _ in range(self.config.epochs):
            optimiser.zero_grad()
            losses = []
            for _, features, adjacency, labels_tensor in train:
                mask = labels_tensor >= 0
                losses.append(loss_function(self.model(features, adjacency)[mask], labels_tensor[mask]))
            torch.stack(losses).mean().backward()
            optimiser.step()
        calibration_raw, calibration_y = self._predict_samples(calibration)
        self.calibrator = LogisticRegression(random_state=self.config.random_state).fit(calibration_raw.reshape(-1, 1), calibration_y)
        test_raw, test_y = self._predict_samples(test)
        test_pd = self.calibrator.predict_proba(test_raw.reshape(-1, 1))[:, 1]
        self.metrics = {
            "candidate_only": True,
            "test_rows": int(len(test_y)),
            "test_brier": round(float(brier_score_loss(test_y, test_pd)), 4),
            "test_roc_auc": round(float(roc_auc_score(test_y, test_pd)), 4) if len(np.unique(test_y)) == 2 else "undefined_single_class",
            "test_average_precision": round(float(average_precision_score(test_y, test_pd)), 4) if len(np.unique(test_y)) == 2 else "undefined_single_class",
        }
        return self

    def _predict_samples(self, samples: list[tuple[str, torch.Tensor, torch.Tensor, torch.Tensor]]) -> tuple[np.ndarray, np.ndarray]:
        assert self.model is not None
        self.model.eval()
        predictions, labels = [], []
        with torch.no_grad():
            for _, features, adjacency, targets in samples:
                mask = targets >= 0
                predictions.extend(torch.sigmoid(self.model(features, adjacency)[mask]).tolist())
                labels.extend(targets[mask].tolist())
        return np.asarray(predictions), np.asarray(labels, dtype=int)

    def save(self, output_dir: Path) -> None:
        assert self.model is not None and self.calibrator is not None
        output_dir.mkdir(parents=True, exist_ok=True)
        torch.save({"model_state": self.model.state_dict(), "config": self.config}, output_dir / "graphsage_candidate.pt")
        (output_dir / "graphsage_candidate_metrics.json").write_text(
            __import__("json").dumps({"metrics": self.metrics, "deployment_status": "validation_gated_not_used_for_scoring"}, indent=2),
            encoding="utf-8",
        )
