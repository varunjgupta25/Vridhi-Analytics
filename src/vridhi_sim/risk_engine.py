"""Phase 2 point-in-time risk engine for synthetic research data.

The implementation intentionally separates tabular PD estimation, graph-derived
signals, and lending policy. Its explanations use XGBoost's native TreeSHAP
contributions, avoiding a runtime dependency on a dashboarding library.
"""

from __future__ import annotations

import csv
import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

import joblib
import numpy as np
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import average_precision_score, brier_score_loss, roc_auc_score
from xgboost import DMatrix, XGBClassifier


FEATURE_COLUMNS = (
    "cash_balance",
    "income_inr",
    "expense_inr",
    "net_cash_flow_inr",
    "income_volatility_3m",
    "missed_utility_payments",
    "overdue_installments",
    "drought_severity",
    "repayment_ability_proxy",
    "buyer_network_stress",
    "buyer_network_coverage",
)

REASON_TEXT = {
    "cash_balance": ("Available cash balance was supportive.", "Available cash balance was lower than the recent borrower profile."),
    "income_inr": ("Recent cash inflow was supportive.", "Recent cash inflow was lower than the recent borrower profile."),
    "expense_inr": ("Recent expense level was supportive.", "Recent expense level increased repayment pressure."),
    "net_cash_flow_inr": ("Net cash flow was supportive.", "Net cash flow increased repayment pressure."),
    "income_volatility_3m": ("Income volatility was supportive.", "Recent income was volatile."),
    "missed_utility_payments": ("Utility-payment consistency was supportive.", "Recent utility payments were missed."),
    "overdue_installments": ("Recent repayment record was supportive.", "Recent repayment instalments were overdue."),
    "drought_severity": ("Local climate conditions were supportive.", "Recent local climate stress was elevated."),
    "repayment_ability_proxy": ("Simulated liquidity relative to repayment was supportive.", "Simulated liquidity relative to repayment was constrained."),
    "buyer_network_stress": ("Observed buyer-network stress was low.", "Observed buyer-network stress was elevated."),
    "buyer_network_coverage": ("Observed buyer-network coverage was informative.", "Buyer-network coverage was limited; this signal has low confidence."),
}


@dataclass(frozen=True)
class RiskEngineConfig:
    random_state: int = 42
    max_relational_delta: float = 0.03
    relational_adjustment_enabled: bool = False
    n_estimators: int = 100
    max_depth: int = 3


def _read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def _subtract_months(month: str, count: int) -> str:
    year, number, _ = (int(part) for part in month.split("-"))
    absolute = year * 12 + (number - 1) - count
    return f"{absolute // 12:04d}-{absolute % 12 + 1:02d}-01"


def _numeric(row: dict[str, str], key: str) -> float:
    return float(row[key])


def build_learning_dataset(dataset_dir: Path) -> list[dict[str, Any]]:
    """Create rows at month t with synthetic 30DPD target from month t + 1."""
    dataset_dir = Path(dataset_dir)
    snapshots = _read_csv(dataset_dir / "node_month.csv")
    labels = _read_csv(dataset_dir / "borrower_month_labels.csv")
    nodes = _read_csv(dataset_dir / "nodes.csv")
    edges = _read_csv(dataset_dir / "edges.csv")
    snapshot_index = {(row["month"], row["entity_id"]): row for row in snapshots}

    labels_by_farmer: dict[str, list[dict[str, str]]] = {}
    for label in labels:
        labels_by_farmer.setdefault(label["farmer_id"], []).append(label)
    rows: list[dict[str, Any]] = []
    for farmer_id, farmer_labels in labels_by_farmer.items():
        farmer_labels.sort(key=lambda item: item["month"])
        for current, next_label in zip(farmer_labels, farmer_labels[1:]):
            snapshot = snapshot_index.get((current["month"], farmer_id))
            if snapshot is None:
                continue
            row: dict[str, Any] = {
                "farmer_id": farmer_id,
                "month": current["month"],
                "target_30dpd_next_month": int(next_label["synthetic_30dpd"]),
            }
            for feature in FEATURE_COLUMNS[:-2]:
                row[feature] = _numeric(snapshot, feature)
            rows.append(row)

    _add_relational_features(rows, snapshots, edges, nodes)
    return sorted(rows, key=lambda item: (item["month"], item["farmer_id"]))


def _add_relational_features(
    rows: list[dict[str, Any]],
    snapshots: list[dict[str, str]],
    edges: list[dict[str, str]],
    nodes: list[dict[str, str]],
) -> None:
    """Add past-only crop-buyer stress without revealing buyer identities.

    This is the bounded relational layer. It is not presented as a validated
    GNN, because the synthetic data does not support that production claim.
    """
    entity_type = {node["entity_id"]: node["entity_type"] for node in nodes}
    state = {(row["month"], row["entity_id"]): row for row in snapshots}
    crop_edges = [
        edge
        for edge in edges
        if edge["transaction_type"] == "crop_sale" and entity_type.get(edge["source_id"]) == "wholesaler"
    ]
    edges_by_farmer: dict[str, list[dict[str, str]]] = {}
    for edge in crop_edges:
        edges_by_farmer.setdefault(edge["target_id"], []).append(edge)
    for row in rows:
        month = str(row["month"])
        window_start = _subtract_months(month, 3)
        prior_month = _subtract_months(month, 1)
        buyers = {
            edge["source_id"]
            for edge in edges_by_farmer.get(str(row["farmer_id"]), [])
            if window_start <= edge["timestamp"][:10] < month
        }
        stress_values: list[float] = []
        for buyer_id in buyers:
            buyer = state.get((prior_month, buyer_id))
            if buyer is None:
                continue
            liquidity_stress = 1.0 - min(_numeric(buyer, "cash_balance") / 250_000.0, 1.0)
            cashflow_stress = 1.0 if _numeric(buyer, "net_cash_flow_inr") < 0 else 0.0
            stress_values.append(0.7 * liquidity_stress + 0.3 * cashflow_stress)
        row["buyer_network_stress"] = round(float(np.mean(stress_values)), 4) if stress_values else 0.0
        row["buyer_network_coverage"] = min(len(stress_values), 3) / 3.0


def _matrix(rows: list[dict[str, Any]]) -> np.ndarray:
    return np.asarray([[float(row[feature]) for feature in FEATURE_COLUMNS] for row in rows], dtype=np.float64)


class RiskEngine:
    """Calibrated XGBoost PD model with an optional capped relational overlay."""

    def __init__(self, config: RiskEngineConfig = RiskEngineConfig()):
        self.config = config
        self.base_model: XGBClassifier | None = None
        self.calibrator: LogisticRegression | None = None
        self.metrics: dict[str, float | int | str] = {}
        self.training_cutoffs: dict[str, str] = {}

    @staticmethod
    def _time_splits(rows: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
        months = sorted({str(row["month"]) for row in rows})
        if len(months) < 8:
            raise ValueError("At least eight distinct months are required for time-aware training.")
        train_end = max(3, int(len(months) * 0.60))
        calibration_end = min(max(train_end + 2, int(len(months) * 0.80)), len(months) - 1)
        train = [row for row in rows if row["month"] in months[:train_end]]
        calibration = [row for row in rows if row["month"] in months[train_end:calibration_end]]
        test = [row for row in rows if row["month"] in months[calibration_end:]]
        if len({row["target_30dpd_next_month"] for row in train}) < 2 or len({row["target_30dpd_next_month"] for row in calibration}) < 2:
            raise ValueError("Synthetic scenario lacks both classes in train/calibration windows; change scenario parameters.")
        return train, calibration, test

    def fit(self, rows: list[dict[str, Any]]) -> "RiskEngine":
        train, calibration, test = self._time_splits(rows)
        self.training_cutoffs = {
            "train_through": str(max(row["month"] for row in train)),
            "calibration_through": str(max(row["month"] for row in calibration)),
            "test_from": str(min(row["month"] for row in test)),
        }
        y_train = np.asarray([row["target_30dpd_next_month"] for row in train], dtype=int)
        scale = max(1.0, float(np.sum(y_train == 0)) / max(float(np.sum(y_train == 1)), 1.0))
        self.base_model = XGBClassifier(
            n_estimators=self.config.n_estimators,
            max_depth=self.config.max_depth,
            learning_rate=0.06,
            subsample=0.9,
            colsample_bytree=0.9,
            objective="binary:logistic",
            eval_metric="logloss",
            scale_pos_weight=scale,
            random_state=self.config.random_state,
            n_jobs=1,
        )
        self.base_model.fit(_matrix(train), y_train)
        calibration_raw = self.base_model.predict_proba(_matrix(calibration))[:, 1]
        self.calibrator = LogisticRegression(random_state=self.config.random_state)
        self.calibrator.fit(calibration_raw.reshape(-1, 1), np.asarray([row["target_30dpd_next_month"] for row in calibration], dtype=int))

        test_pd = self.predict_probability(test)
        test_y = np.asarray([row["target_30dpd_next_month"] for row in test], dtype=int)
        self.metrics = {
            "training_rows": len(train),
            "calibration_rows": len(calibration),
            "test_rows": len(test),
            "test_default_rate": round(float(np.mean(test_y)), 4),
            "test_brier": round(float(brier_score_loss(test_y, test_pd)), 4),
            "test_roc_auc": round(float(roc_auc_score(test_y, test_pd)), 4) if len(np.unique(test_y)) == 2 else "undefined_single_class",
            "test_average_precision": round(float(average_precision_score(test_y, test_pd)), 4) if len(np.unique(test_y)) == 2 else "undefined_single_class",
        }
        return self

    def predict_probability(self, rows: list[dict[str, Any]]) -> np.ndarray:
        if self.base_model is None or self.calibrator is None:
            raise RuntimeError("Train the risk engine before scoring.")
        raw = self.base_model.predict_proba(_matrix(rows))[:, 1]
        return self.calibrator.predict_proba(raw.reshape(-1, 1))[:, 1]

    def score(self, rows: list[dict[str, Any]], apply_relational_adjustment: bool | None = None) -> list[dict[str, Any]]:
        """Return research scores. All outputs are explicitly manual-review only."""
        if self.base_model is None:
            raise RuntimeError("Train the risk engine before scoring.")
        use_adjustment = self.config.relational_adjustment_enabled if apply_relational_adjustment is None else apply_relational_adjustment
        base_pd = self.predict_probability(rows)
        scores: list[dict[str, Any]] = []
        for row, probability in zip(rows, base_pd):
            stress = float(row["buyer_network_stress"])
            coverage = float(row["buyer_network_coverage"])
            delta = float(np.clip((stress - 0.5) * 2.0 * coverage * self.config.max_relational_delta, -self.config.max_relational_delta, self.config.max_relational_delta))
            final_pd = float(np.clip(probability + delta, 0.001, 0.999)) if use_adjustment else float(probability)
            band = "low" if final_pd < 0.15 else "moderate" if final_pd < 0.35 else "high"
            scores.append(
                {
                    "farmer_id": row["farmer_id"],
                    "month": row["month"],
                    "tabular_pd": round(float(probability), 6),
                    "relational_delta": round(delta if use_adjustment else 0.0, 6),
                    "risk_pd": round(final_pd, 6),
                    "synthetic_score_300_900": int(round(300 + 600 * (1.0 - final_pd))),
                    "risk_band": band,
                    "recommended_action": "manual_review_required",
                    "graph_adjustment_applied": bool(use_adjustment),
                    "reason_codes": json.dumps(self.explain(row), ensure_ascii=False),
                }
            )
        return scores

    def explain(self, row: dict[str, Any], top_k: int = 3) -> list[dict[str, str | float]]:
        """Native XGBoost TreeSHAP explanation of the tabular model.

        Calibration and any relationship overlay are stated separately in the
        score record so they cannot be mistaken for causal borrower reasons.
        """
        if self.base_model is None:
            raise RuntimeError("Train the risk engine before explaining.")
        contributions = self.base_model.get_booster().predict(DMatrix(_matrix([row])), pred_contribs=True)[0][:-1]
        top_indices = np.argsort(np.abs(contributions))[::-1][:top_k]
        reasons: list[dict[str, str | float]] = []
        for index in top_indices:
            feature = FEATURE_COLUMNS[int(index)]
            contribution = float(contributions[index])
            supportive, adverse = REASON_TEXT[feature]
            reasons.append(
                {
                    "feature": feature,
                    "direction": "increases_risk" if contribution > 0 else "decreases_risk",
                    "message": adverse if contribution > 0 else supportive,
                    "contribution_log_odds": round(contribution, 4),
                }
            )
        return reasons

    def save(self, output_dir: Path) -> Path:
        if self.base_model is None or self.calibrator is None:
            raise RuntimeError("Train the risk engine before saving it.")
        output_dir.mkdir(parents=True, exist_ok=True)
        joblib.dump({"base_model": self.base_model, "calibrator": self.calibrator, "config": self.config}, output_dir / "risk_engine.joblib")
        metadata = {
            "synthetic_research_only": True,
            "feature_columns": list(FEATURE_COLUMNS),
            "metrics": self.metrics,
            "training_cutoffs": self.training_cutoffs,
            "explanations": "Native XGBoost TreeSHAP feature contributions for the tabular model only.",
            "relational_layer": {
                "type": "past_only_interpretable_buyer_network_feature",
                "default_enabled": self.config.relational_adjustment_enabled,
                "maximum_probability_delta": self.config.max_relational_delta,
                "warning": "Not a validated GNN and not authorised for autonomous credit decisions.",
            },
            "model_configuration": asdict(self.config),
        }
        (output_dir / "risk_engine_metadata.json").write_text(json.dumps(metadata, indent=2), encoding="utf-8")
        return output_dir

    @classmethod
    def load(cls, artifact_dir: Path) -> "RiskEngine":
        """Load a reviewed research artifact for read-only scoring."""
        saved = joblib.load(Path(artifact_dir) / "risk_engine.joblib")
        engine = cls(saved["config"])
        engine.base_model = saved["base_model"]
        engine.calibrator = saved["calibrator"]
        return engine


def write_scores(path: Path, scores: list[dict[str, Any]]) -> None:
    if not scores:
        return
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(scores[0]))
        writer.writeheader()
        writer.writerows(scores)
