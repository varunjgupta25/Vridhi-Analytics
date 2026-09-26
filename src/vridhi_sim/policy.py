"""Phase 7 manual-review policy, explanation drafts, fairness diagnostics, and audit records.

Nothing in this module approves, declines, prices, or modifies a loan.  It only
prioritises a human review and records the safeguards around that review.
"""

from __future__ import annotations

import csv
import hashlib
import json
import uuid
from collections import Counter, defaultdict
from datetime import UTC, datetime
from functools import lru_cache
from pathlib import Path
from typing import Any


POLICY_CONTRACT_PATH = Path(__file__).resolve().parents[2] / "contracts" / "manual_review_policy.json"
CONTEXTUAL_FEATURES = {"drought_severity", "buyer_network_stress", "buyer_network_coverage"}


def _now() -> str:
    return datetime.now(UTC).isoformat()


@lru_cache(maxsize=1)
def load_policy_contract(path: Path = POLICY_CONTRACT_PATH) -> dict[str, Any]:
    """Load a policy contract and reject any unsafe automated-decision setting."""
    contract = json.loads(Path(path).read_text(encoding="utf-8"))
    required = {"policy_id", "version", "automatic_approval", "automatic_decline", "group_specific_thresholds", "review_priorities", "human_reviewer_must_confirm", "never_use_as_sole_adverse_reason"}
    missing = required - set(contract)
    if missing:
        raise ValueError(f"Policy contract is missing required fields: {', '.join(sorted(missing))}")
    if contract["automatic_approval"] or contract["automatic_decline"] or contract["group_specific_thresholds"]:
        raise ValueError("Vridhi's synthetic policy contract must not enable automated decisions or group-specific thresholds.")
    return contract


def _reasons(score: dict[str, Any]) -> list[dict[str, Any]]:
    raw = score.get("reason_codes", "[]")
    if isinstance(raw, list):
        return raw
    try:
        value = json.loads(str(raw))
        return value if isinstance(value, list) else []
    except json.JSONDecodeError:
        return []


def review_priority(risk_pd: float, rules: dict[str, Any] | None = None) -> str:
    """Prioritisation only. The same thresholds apply to every group."""
    rules = rules or load_policy_contract()["review_priorities"]
    if risk_pd >= float(rules["priority"]["risk_pd_gte"]):
        return "priority"
    if risk_pd >= float(rules["elevated"]["risk_pd_gte"]):
        return "elevated"
    return "standard"


def adverse_action_draft(score: dict[str, Any]) -> dict[str, Any]:
    """Make a reviewer-facing explanation draft without inventing a final outcome."""
    direct_factors: list[dict[str, str]] = []
    contextual_factors: list[dict[str, str]] = []
    for reason in _reasons(score):
        if reason.get("direction") != "increases_risk":
            continue
        item = {"feature": str(reason.get("feature", "unknown")), "message": str(reason.get("message", ""))}
        (contextual_factors if item["feature"] in CONTEXTUAL_FEATURES else direct_factors).append(item)
    contract = load_policy_contract()
    return {
        "status": "DRAFT_FOR_HUMAN_REVIEW_NOT_A_FINAL_ADVERSE_ACTION",
        "plain_language_notice": "This score does not make a lending decision. A qualified reviewer must verify the information and applicable policy.",
        "review_factors": direct_factors,
        "contextual_factors_not_sole_reasons": contextual_factors,
        "never_use_as_sole_adverse_reason": contract["never_use_as_sole_adverse_reason"],
        "correction_path": "Provide a lender-approved route for the applicant to ask questions or correct inaccurate data before any final decision.",
    }


def evaluate_manual_review(score: dict[str, Any]) -> dict[str, Any]:
    """Return a policy record with an invariant: no automatic lending action."""
    contract = load_policy_contract()
    risk_pd = float(score["risk_pd"])
    return {
        "policy_id": contract["policy_id"],
        "policy_version": contract["version"],
        "policy_contract_sha256": hashlib.sha256(POLICY_CONTRACT_PATH.read_bytes()).hexdigest(),
        "policy_status": "MANUAL_REVIEW_REQUIRED",
        "final_lending_decision": "NOT_MADE",
        "automatic_approval": False,
        "automatic_decline": False,
        "group_specific_thresholds": False,
        "review_priority": review_priority(risk_pd, contract["review_priorities"]),
        "risk_pd": round(risk_pd, 6),
        "human_reviewer_must_confirm": contract["human_reviewer_must_confirm"],
        "adverse_action_draft": adverse_action_draft(score),
    }


def audit_record(score: dict[str, Any], policy: dict[str, Any], actor: str) -> dict[str, Any]:
    """Create a minimised audit event: no raw financial feature values are stored."""
    subject = f"{score.get('farmer_id', '')}|{score.get('month', '')}"
    explanation = json.dumps(_reasons(score), sort_keys=True)
    return {
        "event_type": "manual_review_policy_evaluated",
        "audit_id": f"audit-{uuid.uuid4()}",
        "evaluated_at": _now(),
        "actor": actor,
        "subject_reference_sha256": hashlib.sha256(subject.encode()).hexdigest(),
        "policy_id": policy["policy_id"],
        "policy_version": policy["policy_version"],
        "review_priority": policy["review_priority"],
        "final_lending_decision": policy["final_lending_decision"],
        "risk_pd": policy["risk_pd"],
        "explanation_sha256": hashlib.sha256(explanation.encode()).hexdigest(),
        "contains_raw_financial_payload": False,
    }


def _ratio(numerator: float, denominator: float) -> float | None:
    return round(numerator / denominator, 6) if denominator else None


def _scenario_pincode(row: dict[str, Any]) -> str:
    explicit = row.get("pincode")
    if explicit not in (None, ""):
        return str(explicit)
    parts = str(row.get("farmer_id", "")).split(":")
    return parts[1] if len(parts) == 3 else "unknown"


def fairness_diagnostic(
    decisions: list[dict[str, Any]], learning_rows: list[dict[str, Any]], minimum_group_size: int = 30
) -> dict[str, Any]:
    """Report group coverage and routing parity; it does not claim legal fairness validation.

    PIN-code cohorts are scenario partitions, not protected-class labels. The
    diagnostic checks that identical policy thresholds were applied and flags
    thin cohorts for human model-risk review.
    """
    pincode_by_subject = {(str(row["farmer_id"]), str(row["month"])): _scenario_pincode(row) for row in learning_rows}
    outcome_by_subject = {(str(row["farmer_id"]), str(row["month"])): int(row["target_30dpd_next_month"]) for row in learning_rows}
    groups: dict[str, list[dict[str, Any]]] = defaultdict(list)
    resolved_decisions: list[dict[str, Any]] = []
    for decision in decisions:
        key = (str(decision["farmer_id"]), str(decision["month"]))
        resolved = {**decision, "outcome": outcome_by_subject.get(key)}
        resolved_decisions.append(resolved)
        groups[pincode_by_subject.get(key, "unknown")].append(resolved)

    def metrics(rows: list[dict[str, Any]]) -> dict[str, Any]:
        count = len(rows)
        outcomes = [row["outcome"] for row in rows if row["outcome"] is not None]
        return {
            "records": count,
            "mean_risk_pd": round(sum(float(row["policy"]["risk_pd"]) for row in rows) / max(count, 1), 6),
            "manual_review_rate": round(sum(row["policy"]["policy_status"] == "MANUAL_REVIEW_REQUIRED" for row in rows) / max(count, 1), 6),
            "priority_review_rate": round(sum(row["policy"]["review_priority"] == "priority" for row in rows) / max(count, 1), 6),
            "synthetic_outcome_rate": round(sum(outcomes) / len(outcomes), 6) if outcomes else None,
        }

    overall = metrics(resolved_decisions)
    cohort_metrics: dict[str, Any] = {}
    alerts: list[str] = []
    for group, rows in sorted(groups.items()):
        group_metrics = metrics(rows)
        group_metrics["manual_review_rate_ratio_to_overall"] = _ratio(group_metrics["manual_review_rate"], overall["manual_review_rate"])
        group_metrics["priority_review_rate_ratio_to_overall"] = _ratio(group_metrics["priority_review_rate"], overall["priority_review_rate"])
        group_metrics["coverage_status"] = "SUFFICIENT_FOR_DIAGNOSTIC" if len(rows) >= minimum_group_size else "INSUFFICIENT_COVERAGE"
        if len(rows) < minimum_group_size:
            alerts.append(f"{group}: fewer than {minimum_group_size} records")
        cohort_metrics[group] = group_metrics
    decision_counts = Counter(row["policy"]["final_lending_decision"] for row in decisions)
    return {
        "generated_at": _now(),
        "scope": "synthetic research diagnostic only",
        "fairness_claim": "NOT_ESTABLISHED: scenario PIN-code cohorts are not protected-class labels and synthetic outcomes cannot validate real-world fairness.",
        "group_definition": "pincode scenario partition",
        "policy_thresholds_group_specific": False,
        "final_lending_decision_counts": dict(decision_counts),
        "overall": overall,
        "cohorts": cohort_metrics,
        "alerts": alerts,
        "overall_status": "REVIEW_REQUIRED",
        "automatic_action": "DISABLED",
    }


def read_scores(path: Path) -> list[dict[str, str]]:
    with Path(path).open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def write_json(path: Path, value: Any) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2), encoding="utf-8")
    return path


def write_audit_jsonl(path: Path, records: list[dict[str, Any]]) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for record in records:
            handle.write(json.dumps(record) + "\n")
    return path
