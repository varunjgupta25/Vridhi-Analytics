from __future__ import annotations

import json

from vridhi_sim.security import SlidingWindowRateLimiter, TamperEvidentAuditLedger, sign_partner_webhook, verify_partner_webhook


def test_partner_signature_is_verified_and_tampering_is_rejected() -> None:
    event = {"event_id": "event-001", "data_classification": "synthetic"}
    signature = sign_partner_webhook("sandbox-lender", event, "unit-test-secret")
    assert verify_partner_webhook("sandbox-lender", event, signature, "unit-test-secret")
    assert not verify_partner_webhook("sandbox-lender", {**event, "event_id": "changed"}, signature, "unit-test-secret")


def test_rate_limiter_and_hash_chain_detect_tampering(tmp_path) -> None:
    limiter = SlidingWindowRateLimiter(limit=2, window_seconds=10)
    assert limiter.allow("client", now=1)[0]
    assert limiter.allow("client", now=2)[0]
    assert not limiter.allow("client", now=3)[0]
    assert limiter.allow("client", now=12)[0]

    path = tmp_path / "ledger.jsonl"
    ledger = TamperEvidentAuditLedger(path)
    ledger.append({"event_type": "first"})
    ledger.append({"event_type": "second"})
    assert ledger.verify()["valid"] is True
    records = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]
    records[0]["event"]["event_type"] = "tampered"
    path.write_text("\n".join(json.dumps(record) for record in records) + "\n", encoding="utf-8")
    assert ledger.verify()["valid"] is False
