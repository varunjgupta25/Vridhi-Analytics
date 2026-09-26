from __future__ import annotations

from vridhi_sim.mlops import create_promotion_request, delayed_label_performance, drift_report, population_stability_index


def _row(cash: float) -> dict:
    return {
        "farmer_id": "farmer:413001:001", "month": "2026-07-01", "cash_balance": cash,
        "income_inr": 1000, "expense_inr": 600, "net_cash_flow_inr": 400, "income_volatility_3m": 0.1,
        "missed_utility_payments": 0, "overdue_installments": 0, "drought_severity": 0.1,
        "repayment_ability_proxy": 1.2, "buyer_network_stress": 0.0, "buyer_network_coverage": 0.0,
        "target_30dpd_next_month": 0,
    }


def test_drift_alerts_require_review_and_never_retrain() -> None:
    reference = [_row(float(index)) for index in range(1, 21)]
    current = [_row(9_999.0) for _ in range(20)]
    report = drift_report(reference, current)
    assert population_stability_index([1, 2, 3], [100, 100, 100]) > 0
    assert report["overall_status"] == "REVIEW_REQUIRED"
    assert report["automatic_retraining"] == "DISABLED"


def test_delayed_outcome_and_promotion_are_human_gated(tmp_path) -> None:
    rows = [_row(100), {**_row(200), "farmer_id": "farmer:413001:002", "target_30dpd_next_month": 1}]
    scores = [{"farmer_id": "farmer:413001:001", "month": "2026-07-01", "risk_pd": "0.1"}, {"farmer_id": "farmer:413001:002", "month": "2026-07-01", "risk_pd": "0.8"}]
    performance = delayed_label_performance(scores, rows)
    request = create_promotion_request(tmp_path / "candidate", "model-risk-owner")
    assert performance["status"] == "REVIEW_REQUIRED"
    assert request["status"] == "PENDING_HUMAN_MODEL_RISK_APPROVAL"
    assert request["automatic_promotion"] is False
