"""Unit tests for Phase 8 security & integration assurance controls."""

from __future__ import annotations

import json
from pathlib import Path
import pytest
from fastapi.testclient import TestClient

from vridhi_sim.backend import create_app, SandboxSettings
from vridhi_sim.security import (
    validate_aa_consent_artifact,
    sanitize_kyc_data,
    check_aml_sanctions,
    bhashini_translate,
    run_security_pentest,
    get_kill_switch,
)


def test_aa_consent_validation() -> None:
    valid_consent = {
        "consent_id": "consent_123",
        "borrower_id": "farmer:413001:001",
        "purpose": "CREDIT_ASSESSMENT",
        "expires_at": 0,
    }
    val = validate_aa_consent_artifact(valid_consent)
    assert val["valid"] is True
    assert val["consent_id"] == "consent_123"

    invalid_purpose = {**valid_consent, "purpose": "MARKETING"}
    val_inv = validate_aa_consent_artifact(invalid_purpose)
    assert val_inv["valid"] is False
    assert "Invalid purpose code" in val_inv["reason"]


def test_kyc_sanitization_and_aml() -> None:
    raw_payload = {
        "farmer_id": "farmer:413001:001",
        "aadhaar_number": "123456789012",
        "pan_number": "ABCDE1234F",
    }
    sanitized = sanitize_kyc_data(raw_payload)
    assert "aadhaar_number" not in sanitized
    assert "pan_number" not in sanitized
    assert "masked_aadhaar_hash" in sanitized
    assert "masked_pan_hash" in sanitized

    aml_pass = check_aml_sanctions("farmer:413001:001")
    assert aml_pass["aml_cleared"] is True

    aml_fail = check_aml_sanctions("SANCTIONED_BORROWER_999")
    assert aml_fail["aml_cleared"] is False
    assert aml_fail["status"] == "FLAGGED_HIGH_RISK"


def test_bhashini_localization_mock() -> None:
    res = bhashini_translate("High reliance on seasonal income.", "hi")
    assert res["target_language"] == "hi"
    assert "मौसमी आय" in res["translated_text"]


def test_security_pentest_harness(tmp_path: Path) -> None:
    ledger_path = tmp_path / "test_ledger.jsonl"
    report = run_security_pentest(ledger_path)
    assert report["pentest_status"] == "PASSED"
    assert report["tests"]["hmac_signature_integrity"] == "PASS"
    assert report["tests"]["audit_ledger_tamper_evidence"] == "PASS"


def test_kill_switch_api_flow(tmp_path: Path) -> None:
    ks = get_kill_switch()
    ks.deactivate()
    assert ks.is_active() is False

    settings = SandboxSettings(
        consent_db=tmp_path / "consents.sqlite3",
        security_audit_path=tmp_path / "security.jsonl",
        policy_audit_path=tmp_path / "policy.jsonl",
    )
    app = create_app(settings)
    client = TestClient(app)

    # Get admin token
    token_resp = client.post(
        "/v1/oauth/token",
        data={"grant_type": "client_credentials", "client_id": "sandbox-admin", "client_secret": "sandbox-secret", "scope": "killswitch:manage audit:read"},
    )
    assert token_resp.status_code == 200
    token = token_resp.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    # Activate kill switch
    act_resp = client.post("/v1/admin/kill-switch", json={"action": "ACTIVATE", "reason": "SECURITY_PENTEST"}, headers=headers)
    assert act_resp.status_code == 200
    assert act_resp.json()["status"] == "ACTIVE"
    assert ks.is_active() is True

    # Status check
    status_resp = client.get("/v1/admin/kill-switch", headers=headers)
    assert status_resp.json()["active"] is True

    # Deactivate kill switch
    deact_resp = client.post("/v1/admin/kill-switch", json={"action": "DEACTIVATE"}, headers=headers)
    assert deact_resp.status_code == 200
    assert ks.is_active() is False
