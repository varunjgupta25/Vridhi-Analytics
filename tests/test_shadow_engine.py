"""Unit tests for Phase 9 Shadow-Mode Pilot Engine."""

from __future__ import annotations

from pathlib import Path
import pandas as pd
import pytest

from vridhi_sim.shadow_engine import ShadowPilotEngine, OfficerFeedback


def test_shadow_engine_eval(tmp_path: Path) -> None:
    scores_data = pd.DataFrame({
        "farmer_id": ["f1", "f2", "f3", "f4"],
        "risk_pd": [0.10, 0.45, 0.85, 0.90],
    })
    labels_data = pd.DataFrame({
        "repayment_status_30dpd": [0, 0, 1, 1],
    })

    engine = ShadowPilotEngine()
    
    # Record mock feedback
    engine.record_feedback(
        OfficerFeedback("s1", "officer_1", 5, True, "Helpful TreeSHAP breakdown", "2026-08-02T12:00:00Z")
    )

    report = engine.evaluate_shadow_run(scores_data, labels_data, lender_baseline_pd=[0.15, 0.20, 0.80, 0.30])
    
    assert report["status"] == "SHADOW_PILOT_COMPLETED"
    assert report["total_evaluations"] == 4
    assert "disagreement_rate" in report
    assert report["operational_feedback_summary"]["total_feedbacks"] == 1
    assert report["operational_feedback_summary"]["treeshap_usefulness_pct"] == 1.0

    out_file = tmp_path / "shadow_report.json"
    engine.save_report(report, out_file)
    assert out_file.exists()
