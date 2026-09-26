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


def _build_minimal_engine():
    """Build and return a trained RiskEngine on a minimal synthetic dataset.

    Kept separate so tests that don't need a real engine remain fast.
    """
    from vridhi_sim.risk_engine import RiskEngine, RiskEngineConfig, build_learning_dataset
    from pathlib import Path

    dataset_dir = Path("data/generated/reference")
    if not dataset_dir.exists():
        pytest.skip("Reference dataset not generated; run vridhi-simulate first.")
    rows = build_learning_dataset(dataset_dir)
    return RiskEngine(RiskEngineConfig()).fit(rows), rows


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


def test_latency_is_null_when_no_engine_provided() -> None:
    """When no risk_engine is passed, vridhi_avg_latency_ms must be null (not 0.0 or 14.2).

    The previous implementation timed np.where on an already-computed PD array
    which is not the scoring path.  Without a real engine the latency must be
    explicitly reported as None rather than silently returning a meaningless 0.0.
    """
    risk_pds = [0.1 * (i % 10) for i in range(200)]
    scores_data = _make_scores(risk_pds)

    engine = ShadowPilotEngine()
    report = engine.evaluate_shadow_run(scores_data)  # no risk_engine

    latency = report["latency_metrics"]["vridhi_avg_latency_ms"]
    assert latency is None, (
        "vridhi_avg_latency_ms must be null when risk_engine is not provided; "
        f"got {latency!r}.  Do not time post-processing on a pre-computed array."
    )
    assert report["latency_metrics"]["latency_path_complete"] is False
    # The note must explain why latency is null
    method_note = report["latency_metrics"]["latency_measurement_method"]
    assert "risk_engine" in method_note.lower() or "not provided" in method_note.lower(), (
        "latency_measurement_method must explain that risk_engine was not available"
    )
    # Baseline latency still null
    assert report["latency_metrics"]["baseline_avg_latency_ms"] is None


def test_latency_is_real_and_nonzero_when_engine_provided() -> None:
    """When a real RiskEngine is provided, latency must cover the full scoring path
    (XGBoost predict_proba + Platt calibration + TreeSHAP) and produce a
    strictly positive, non-fabricated value.
    """
    risk_engine, rows = _build_minimal_engine()

    # Build scores_df from the real engine output
    score_records = risk_engine.score(rows)
    scores_df = pd.DataFrame([{"farmer_id": r["farmer_id"], "risk_pd": r["risk_pd"]} for r in score_records])

    pilot = ShadowPilotEngine()
    report = pilot.evaluate_shadow_run(
        scores_df,
        risk_engine=risk_engine,
        sample_rows=rows,
    )

    latency = report["latency_metrics"]["vridhi_avg_latency_ms"]
    assert isinstance(latency, float), f"latency must be a float, got {type(latency)}"
    assert latency > 0, f"measured latency must be strictly positive, got {latency}"
    assert latency != 14.2, "latency must NOT be the old hardcoded constant 14.2"
    assert report["latency_metrics"]["latency_path_complete"] is True

    method = report["latency_metrics"]["latency_measurement_method"]
    assert "perf_counter" in method.lower(), "method must reference time.perf_counter()"
    # Confirm it covers the full path, not just post-processing
    assert "xgb" in method.lower() or "predict_proba" in method.lower(), (
        "method description must confirm XGBoost/calibration was included in the timed path"
    )


def test_latency_measurement_method_is_documented() -> None:
    """The latency_metrics block must always include a latency_measurement_method string."""
    scores_data = _make_scores([0.2, 0.5, 0.8])
    engine = ShadowPilotEngine()
    report = engine.evaluate_shadow_run(scores_data)

    assert "latency_measurement_method" in report["latency_metrics"], (
        "latency_metrics must document how (or why not) latency was measured"
    )
    method = report["latency_metrics"]["latency_measurement_method"]
    assert isinstance(method, str) and len(method) > 10


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
