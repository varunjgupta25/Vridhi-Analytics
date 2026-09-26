from __future__ import annotations

import json

from vridhi_sim.policy import adverse_action_draft, audit_record, evaluate_manual_review, fairness_diagnostic, load_policy_contract


def _score(pd: float = 0.6) -> dict:
    return {
        "farmer_id": "farmer:413001:001",
        "month": "2026-07-01",
        "risk_pd": pd,
        "reason_codes": json.dumps([
            {"feature": "overdue_installments", "direction": "increases_risk", "message": "Recent repayment instalments were overdue."},
            {"feature": "drought_severity", "direction": "increases_risk", "message": "Recent local climate stress was elevated."},
        ]),
    }


def test_policy_is_manual_review_only_and_context_is_not_a_sole_reason() -> None:
    contract = load_policy_contract()
    policy = evaluate_manual_review(_score())
    draft = adverse_action_draft(_score())
    assert policy["final_lending_decision"] == "NOT_MADE"
    assert policy["automatic_approval"] is False
    assert policy["automatic_decline"] is False
    assert policy["review_priority"] == "priority"
    assert policy["policy_version"] == contract["version"]
    assert draft["review_factors"][0]["feature"] == "overdue_installments"
    assert draft["contextual_factors_not_sole_reasons"][0]["feature"] == "drought_severity"


def test_fairness_diagnostic_is_group_neutral_and_audit_is_minimised() -> None:
    score = _score(0.2)
    policy = evaluate_manual_review(score)
    decisions = [{"farmer_id": score["farmer_id"], "month": score["month"], "policy": policy}]
    rows = [{"farmer_id": score["farmer_id"], "month": score["month"], "pincode": "413001", "target_30dpd_next_month": 0}]
    report = fairness_diagnostic(decisions, rows, minimum_group_size=2)
    audit = audit_record(score, policy, "test")
    assert report["policy_thresholds_group_specific"] is False
    assert report["overall_status"] == "REVIEW_REQUIRED"
    assert audit["contains_raw_financial_payload"] is False
    assert "farmer_id" not in audit
