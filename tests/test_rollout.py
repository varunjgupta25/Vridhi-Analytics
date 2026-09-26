"""Unit tests for Phase 10 Controlled Production Rollout & Governance."""

from __future__ import annotations

from pathlib import Path
import pytest

from vridhi_sim.rollout import ProductionRolloutManager


def test_borrower_eligibility() -> None:
    mgr = ProductionRolloutManager()
    
    # Approved pincode within volume limit
    ok = mgr.check_borrower_eligibility(413001, sample_percentile=4.0)
    assert ok["eligible"] is True

    # Pincode outside approved pilot list
    bad_pin = mgr.check_borrower_eligibility(999999, sample_percentile=4.0)
    assert bad_pin["eligible"] is False
    assert "outside approved pilot zone" in bad_pin["reason"]

    # Sample percentile exceeds Stage 1 (5%) limit
    vol_exceeded = mgr.check_borrower_eligibility(413001, sample_percentile=10.0)
    assert vol_exceeded["eligible"] is False
    assert "exceeds stage limit" in vol_exceeded["reason"]


def test_automated_rollback_trigger() -> None:
    mgr = ProductionRolloutManager()
    
    # Normal metrics -> Healthy
    h = mgr.evaluate_health_and_rollback(brier_score=0.08, psi_drift=0.05, error_rate_pct=0.1)
    assert h["status"] == "HEALTHY"

    # High PSI drift -> Rollback triggered
    rb = mgr.evaluate_health_and_rollback(psi_drift=0.35)
    assert rb["status"] == "ROLLED_BACK"
    assert mgr.rolled_back is True
    assert mgr.current_stage == "STAGE_0_SHADOW_ONLY"

    # Subsequent eligibility check rejected due to rollback
    rej = mgr.check_borrower_eligibility(413001, sample_percentile=1.0)
    assert rej["eligible"] is False
    assert "SYSTEM_ROLLED_BACK" in rej["reason"]


def test_governance_certificate(tmp_path: Path) -> None:
    mgr = ProductionRolloutManager()
    cert = mgr.generate_governance_certificate()
    assert cert["active_rollout_stage"] == "STAGE_1_LIMITED_PILOT_5PCT"
    assert "GOV-CERT-2026" in cert["certificate_id"]

    out_file = tmp_path / "cert.json"
    mgr.save_certificate(cert, out_file)
    assert out_file.exists()
