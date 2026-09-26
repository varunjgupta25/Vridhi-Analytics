"""Phase 5 monitoring and governance utilities.

Alerts trigger review, never automatic retraining or automatic model promotion.
"""

from __future__ import annotations

import json
import math
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import numpy as np
from sklearn.metrics import average_precision_score, brier_score_loss, roc_auc_score

from .risk_engine import FEATURE_COLUMNS, RiskEngine


def _distribution(values: list[float], edges: list[float]) -> list[float]:
    counts = [0] * (len(edges) + 1)
    for value in values:
        bucket = next((index for index, edge in enumerate(edges) if value <= edge), len(edges))
        counts[bucket] += 1
    total = max(sum(counts), 1)
    return [max(count / total, 1e-6) for count in counts]


def population_stability_index(reference: list[float], current: list[float], bins: int = 10) -> float:
    """Calculate PSI with reference quantile bins, robust to repeated values."""
    if not reference or not current:
        return math.nan
    edges = sorted({float(np.quantile(reference, step / bins)) for step in range(1, bins)})
    expected, actual = _distribution(reference, edges), _distribution(current, edges)
    return float(sum((a - e) * math.log(a / e) for e, a in zip(expected, actual)))


def profile_features(rows: list[dict[str, Any]]) -> dict[str, Any]:
    profile: dict[str, Any] = {"row_count": len(rows), "features": {}}
    for feature in FEATURE_COLUMNS:
        values = [float(row[feature]) for row in rows if row.get(feature) not in (None, "")]
        profile["features"][feature] = {
            "missing_rate": round(1 - len(values) / max(len(rows), 1), 6),
            "mean": round(float(np.mean(values)), 6) if values else None,
            "p50": round(float(np.quantile(values, 0.5)), 6) if values else None,
            "p95": round(float(np.quantile(values, 0.95)), 6) if values else None,
            "values": values,
        }
    return profile


def drift_report(reference_rows: list[dict[str, Any]], current_rows: list[dict[str, Any]], psi_alert_threshold: float = 0.20) -> dict[str, Any]:
    reference, current = profile_features(reference_rows), profile_features(current_rows)
    features: dict[str, Any] = {}
    alerts: list[str] = []
    for feature in FEATURE_COLUMNS:
        psi = population_stability_index(reference["features"][feature]["values"], current["features"][feature]["values"])
        missing_delta = current["features"][feature]["missing_rate"] - reference["features"][feature]["missing_rate"]
        status = "alert" if (not math.isnan(psi) and psi >= psi_alert_threshold) or abs(missing_delta) >= 0.05 else "ok"
        if status == "alert":
            alerts.append(feature)
        features[feature] = {"psi": round(psi, 6) if not math.isnan(psi) else None, "missing_rate_delta": round(missing_delta, 6), "status": status}
    return {
        "generated_at": datetime.now(UTC).isoformat(),
        "reference_rows": len(reference_rows),
        "current_rows": len(current_rows),
        "alert_features": alerts,
        "overall_status": "REVIEW_REQUIRED" if alerts else "STABLE",
        "automatic_retraining": "DISABLED",
        "features": features,
    }


def delayed_label_performance(scores: list[dict[str, Any]], learning_rows: list[dict[str, Any]]) -> dict[str, Any]:
    labels = {(str(row["farmer_id"]), str(row["month"])): int(row["target_30dpd_next_month"]) for row in learning_rows}
    matched = [(float(score["risk_pd"]), labels[(str(score["farmer_id"]), str(score["month"]))]) for score in scores if (str(score["farmer_id"]), str(score["month"])) in labels]
    if not matched:
        raise ValueError("No score rows match delayed labels.")
    probabilities, outcomes = np.asarray([item[0] for item in matched]), np.asarray([item[1] for item in matched])
    return {
        "evaluated_rows": len(matched),
        "outcome_rate": round(float(np.mean(outcomes)), 6),
        "brier": round(float(brier_score_loss(outcomes, probabilities)), 6),
        "roc_auc": round(float(roc_auc_score(outcomes, probabilities)), 6) if len(np.unique(outcomes)) == 2 else None,
        "average_precision": round(float(average_precision_score(outcomes, probabilities)), 6) if len(np.unique(outcomes)) == 2 else None,
        "status": "REVIEW_REQUIRED",
        "note": "Performance is measured only after delayed outcomes arrive; no automatic retraining is performed.",
    }


def model_card(engine: RiskEngine, dataset_name: str, training_profile: dict[str, Any] | None = None) -> dict[str, Any]:
    card: dict[str, Any] = {
        "model_name": "vridhi-synthetic-risk-engine",
        "version": datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ"),
        "intended_use": "Synthetic research and lender manual-review support only.",
        "not_for": ["automatic approvals", "automatic declines", "real borrower deployment without validation"],
        "dataset": dataset_name,
        "feature_list": list(FEATURE_COLUMNS),
        "performance": engine.metrics,
        "training_cutoffs": engine.training_cutoffs,
        "governance": {"human_approval_required": True, "auto_retraining": False, "graph_adjustment_default": engine.config.relational_adjustment_enabled},
        # training_profile contains measured wall-clock time and peak memory.
        # If not supplied, the sentinel makes the absence explicit and auditable.
        "training_profile": training_profile if training_profile is not None else {"not_measured": True},
    }
    return card


def write_json(path: Path, payload: dict[str, Any]) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return path


def create_promotion_request(candidate_dir: Path, owner: str, drift: dict[str, Any] | None = None) -> dict[str, Any]:
    """Record a human-approval request; this intentionally never changes production aliases."""
    return {
        "candidate_dir": str(candidate_dir),
        "requested_by": owner,
        "requested_at": datetime.now(UTC).isoformat(),
        "status": "PENDING_HUMAN_MODEL_RISK_APPROVAL",
        "drift_status": drift.get("overall_status") if drift else "NOT_SUPPLIED",
        "automatic_promotion": False,
    }
