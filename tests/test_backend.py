from __future__ import annotations

import json

from cryptography.fernet import Fernet
from fastapi.testclient import TestClient

from vridhi_sim.backend import InMemoryStreamBus, SandboxSettings, create_app
from vridhi_sim.risk_engine import RiskEngine
from vridhi_sim.security import sign_partner_webhook


def _client(tmp_path) -> tuple[TestClient, SandboxSettings]:
    settings = SandboxSettings(
        consent_db=tmp_path / "consents.sqlite3",
        policy_audit_path=tmp_path / "policy_audit.jsonl",
        security_audit_path=tmp_path / "security_audit.jsonl",
    )
    engine = RiskEngine.load("artifacts/risk/reference")
    return TestClient(create_app(settings, engine=engine, stream_bus=InMemoryStreamBus())), settings


def _token(client: TestClient, client_id: str = "sandbox-client", scope: str = "consent:write score:write stream:write stream:read") -> str:
    response = client.post(
        "/v1/oauth/token",
        data={
            "grant_type": "client_credentials",
            "client_id": client_id,
            "client_secret": "sandbox-secret",
            "scope": scope,
        },
    )
    assert response.status_code == 200
    return response.json()["access_token"]


def _envelope(settings: SandboxSettings, consent_id: str, payload: dict, key: str) -> dict:
    ciphertext = Fernet(settings.payload_key.encode()).encrypt(json.dumps(payload).encode()).decode()
    return {"consent_id": consent_id, "ciphertext": ciphertext, "idempotency_key": key}


def test_encrypted_consent_bound_score_and_stream_flow(tmp_path) -> None:
    client, settings = _client(tmp_path)
    headers = {"Authorization": f"Bearer {_token(client)}"}
    consent = client.post(
        "/v1/consents",
        headers=headers,
        json={"purpose": "credit_underwriting", "data_types": ["financial_information", "upi_transaction"]},
    )
    assert consent.status_code == 201
    consent_id = consent.json()["consent_id"]
    payload = {
        "farmer_id": "farmer:413001:001", "month": "2026-07-01", "cash_balance": 25000,
        "income_inr": 4000, "expense_inr": 3100, "net_cash_flow_inr": 900, "income_volatility_3m": 0.2,
        "missed_utility_payments": 0, "overdue_installments": 0, "drought_severity": 0.1,
        "repayment_ability_proxy": 1.1, "buyer_network_stress": 0.0, "buyer_network_coverage": 0.0,
    }
    score = client.post("/v1/scores", headers=headers, json=_envelope(settings, consent_id, payload, "score-event-0001"))
    assert score.status_code == 200
    assert score.json()["recommended_action"] == "manual_review_required"
    assert score.json()["policy"]["final_lending_decision"] == "NOT_MADE"
    assert score.json()["sandbox"] is True
    event = {"event_id": "upi-event-001", "timestamp": "2026-07-01T10:00:00Z", "source_id": payload["farmer_id"], "target_id": "retailer:413001:01", "amount_inr": 250, "transaction_type": "kirana_purchase"}
    ingested = client.post("/v1/upi-events", headers=headers, json=_envelope(settings, consent_id, event, "upi-event-key-001"))
    assert ingested.status_code == 202
    stream = client.get("/v1/streams/upi-transactions/recent", headers=headers)
    assert stream.status_code == 200
    assert stream.json()["events"][0]["event_id"] == "upi-event-001"


def test_duplicate_or_revoked_consent_cannot_be_used(tmp_path) -> None:
    client, settings = _client(tmp_path)
    headers = {"Authorization": f"Bearer {_token(client)}"}
    consent_id = client.post("/v1/consents", headers=headers, json={"purpose": "credit_underwriting", "data_types": ["financial_information"]}).json()["consent_id"]
    payload = {"farmer_id": "farmer:413001:001", "month": "2026-07-01", "cash_balance": 1, "income_inr": 1, "expense_inr": 1, "net_cash_flow_inr": 0, "income_volatility_3m": 0, "missed_utility_payments": 0, "overdue_installments": 0, "drought_severity": 0, "repayment_ability_proxy": 1, "buyer_network_stress": 0, "buyer_network_coverage": 0}
    envelope = _envelope(settings, consent_id, payload, "duplicate-event-001")
    assert client.post("/v1/scores", headers=headers, json=envelope).status_code == 200
    assert client.post("/v1/scores", headers=headers, json=envelope).status_code == 409
    assert client.delete(f"/v1/consents/{consent_id}", headers=headers).status_code == 204
    revoked = client.post("/v1/scores", headers=headers, json=_envelope(settings, consent_id, payload, "revoked-event-001"))
    assert revoked.status_code == 403


def test_phase_four_frontend_is_served_from_the_api(tmp_path) -> None:
    client, _ = _client(tmp_path)
    response = client.get("/app/")
    assert response.status_code == 200
    assert "Rural risk intelligence" in response.text
    policy = client.get("/v1/policy/reference-summary")
    assert policy.status_code == 200
    assert policy.json()["manual_review_only"] is True


def test_admin_only_signed_partner_webhook_and_audit_integrity(tmp_path) -> None:
    client, settings = _client(tmp_path)
    officer_headers = {"Authorization": f"Bearer {_token(client)}"}
    event = {
        "event_id": "partner-event-001",
        "event_type": "synthetic_data_ready",
        "occurred_at": "2026-08-01T10:00:00Z",
        "payload_digest": "a" * 64,
        "data_classification": "synthetic",
    }
    assert client.post("/v1/partner-webhooks/sandbox-lender", headers=officer_headers, json=event).status_code == 403

    admin_token = _token(client, "sandbox-admin", "audit:read retention:run partner:webhook stream:read")
    admin_headers = {
        "Authorization": f"Bearer {admin_token}",
        "X-Vridhi-Signature": sign_partner_webhook("sandbox-lender", event, settings.partner_webhook_secret),
    }
    webhook = client.post("/v1/partner-webhooks/sandbox-lender", headers=admin_headers, json=event)
    assert webhook.status_code == 202
    assert webhook.json()["signature_verified"] is True
    integrity = client.get("/v1/admin/audit-integrity", headers={"Authorization": f"Bearer {admin_token}"})
    assert integrity.status_code == 200
    assert integrity.json()["valid"] is True
