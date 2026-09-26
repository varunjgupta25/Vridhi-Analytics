"""Unit tests for Phase 9 Shadow-Mode Pilot Engine."""

from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest

from vridhi_sim.shadow_engine import ShadowPilotEngine, OfficerFeedback


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

def _make_scores(risk_pds: list[float]) -> pd.DataFrame:
    return pd.DataFrame({
        "farmer_id": [f"f{i}" for i in range(len(risk_pds))],
        "risk_pd": risk_pds,
    })


def _make_labels(outcomes: list[int]) -> pd.DataFrame:
    return pd.DataFrame({"repayment_status_30dpd": outcomes})


# ---------------------------------------------------------------------------
# Core evaluation tests
# ---------------------------------------------------------------------------

def test_shadow_engine_eval_with_real_lender_baseline(tmp_path: Path) -> None:
    """When a real lender baseline is provided, baseline_source must reflect that."""
    scores_data = _make_scores([0.10, 0.45, 0.85, 0.90])
    labels_data = _make_labels([0, 0, 1, 1])

    engine = ShadowPilotEngine()
    engine.record_feedback(
        OfficerFeedback("s1", "officer_1", 5, True, "Helpful TreeSHAP breakdown", "2026-08-02T12:00:00Z")
    )

    report = engine.evaluate_shadow_run(
        scores_data, labels_data, lender_baseline_pd=[0.15, 0.20, 0.80, 0.30]
    )

    assert report["status"] == "SHADOW_PILOT_COMPLETED"
    assert report["total_evaluations"] == 4
    assert "disagreement_rate" in report
    assert report["operational_feedback_summary"]["total_feedbacks"] == 1
    assert report["operational_feedback_summary"]["treeshap_usefulness_pct"] == 1.0

    # Real lender baseline must be labelled correctly
    assert report["baseline_source"] == "real_lender_provided"

    out_file = tmp_path / "shadow_report.json"
    engine.save_report(report, out_file)
    assert out_file.exists()


def test_shadow_engine_synthetic_baseline_is_explicitly_labelled() -> None:
    """When no lender baseline is provided, report must carry the synthetic-placeholder flag.

    This prevents any downstream consumer from presenting the noise-perturbed
    proxy as a real bank or lender comparison.
    """
    scores_data = _make_scores([0.10, 0.45, 0.85, 0.90])

    engine = ShadowPilotEngine()
    report = engine.evaluate_shadow_run(scores_data)

    assert report["baseline_source"] == "synthetic_noise_placeholder", (
        "synthetic noise baseline must be labelled 'synthetic_noise_placeholder' "
        "so it cannot be mistaken for a real lender comparison"
    )
    assert "baseline_note" in report, "A human-readable note explaining the placeholder must be present"
    assert "synthetic" in report["baseline_note"].lower(), (
        "baseline_note must explicitly mention 'synthetic' so it is never misread"
    )


def test_latency_is_measured_not_hardcoded() -> None:
    """vridhi_avg_latency_ms must be a real measurement, not the old hardcoded 14.2.

    The measured value will differ across machines and run sizes, so we only
    assert structural correctness (positive float) and that it is NOT the exact
    old fabricated constant.
    """
    # Use a larger sample so the measurement is non-trivially fast
    risk_pds = [0.1 * (i % 10) for i in range(200)]
    scores_data = _make_scores(risk_pds)

    engine = ShadowPilotEngine()
    report = engine.evaluate_shadow_run(scores_data)

    latency = report["latency_metrics"]["vridhi_avg_latency_ms"]

    assert isinstance(latency, float), "latency must be a float, not None or a string"
    assert latency > 0, "measured latency must be strictly positive"
    assert latency != 14.2, (
        "latency must be a real measurement, not the old hardcoded constant 14.2. "
        f"Got {latency}"
    )
    # Baseline latency must be None because no real lender process exists
    assert report["latency_metrics"]["baseline_avg_latency_ms"] is None, (
        "baseline_avg_latency_ms must be None when no real lender timing is available"
    )


def test_latency_measurement_method_is_documented() -> None:
    """The latency_metrics block must include a human-readable explanation of how latency was measured."""
    scores_data = _make_scores([0.2, 0.5, 0.8])
    engine = ShadowPilotEngine()
    report = engine.evaluate_shadow_run(scores_data)

    assert "latency_measurement_method" in report["latency_metrics"], (
        "latency_metrics must document how latency was measured"
    )
    method = report["latency_metrics"]["latency_measurement_method"]
    assert "perf_counter" in method.lower(), "method description must reference time.perf_counter()"


def test_no_data_returns_early() -> None:
    """Empty scores DataFrame must return NO_DATA without raising."""
    engine = ShadowPilotEngine()
    report = engine.evaluate_shadow_run(pd.DataFrame({"risk_pd": []}))
    assert report["status"] == "NO_DATA"


def test_label_ground_truth_key_present_when_labels_provided() -> None:
    """label_ground_truth block must appear when real 30-DPD labels are supplied."""
    scores_data = _make_scores([0.10, 0.85, 0.90, 0.20])
    labels_data = _make_labels([0, 1, 1, 0])

    engine = ShadowPilotEngine()
    report = engine.evaluate_shadow_run(scores_data, labels_data, lender_baseline_pd=[0.12, 0.70, 0.80, 0.25])

    assert "label_ground_truth" in report
    gt = report["label_ground_truth"]
    assert "vridhi_roc_auc" in gt
    assert "baseline_label" in gt


def test_feedback_summary_empty_when_no_feedback() -> None:
    scores_data = _make_scores([0.3, 0.6])
    engine = ShadowPilotEngine()
    report = engine.evaluate_shadow_run(scores_data)

    feedback = report["operational_feedback_summary"]
    assert feedback["total_feedbacks"] == 0
    assert feedback["average_rating"] == 0.0
