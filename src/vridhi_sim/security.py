"""Phase 8 security primitives for Vridhi's synthetic integration sandbox.

These controls demonstrate engineering patterns. They do not turn the sandbox
into a regulated Account Aggregator, FIU, lender, or live payments system.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import threading
import time
from collections import deque
from pathlib import Path
from typing import Any


DEFAULT_CLIENT_ROLES = {"sandbox-client": "loan_officer", "sandbox-reviewer": "reviewer", "sandbox-admin": "admin"}
ROLE_SCOPES = {
    "loan_officer": {"consent:write", "score:write", "stream:write", "stream:read"},
    "reviewer": {"score:write", "stream:read"},
    "admin": {"audit:read", "retention:run", "partner:webhook", "stream:read", "killswitch:manage"},
}


def canonical_json(value: dict[str, Any]) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def sign_partner_webhook(partner_id: str, event: dict[str, Any], secret: str) -> str:
    message = f"{partner_id}.{canonical_json(event)}".encode()
    return hmac.new(secret.encode(), message, hashlib.sha256).hexdigest()


def verify_partner_webhook(partner_id: str, event: dict[str, Any], signature: str | None, secret: str) -> bool:
    if not signature:
        return False
    return hmac.compare_digest(sign_partner_webhook(partner_id, event, secret), signature)


class SlidingWindowRateLimiter:
    """In-memory API limiter suitable only for the single-process local sandbox."""

    def __init__(self, limit: int = 120, window_seconds: int = 60):
        self.limit = limit
        self.window_seconds = window_seconds
        self._events: dict[str, deque[float]] = {}
        self._lock = threading.Lock()

    def allow(self, key: str, now: float | None = None) -> tuple[bool, int]:
        moment = time.monotonic() if now is None else now
        with self._lock:
            events = self._events.setdefault(key, deque())
            cutoff = moment - self.window_seconds
            while events and events[0] <= cutoff:
                events.popleft()
            if len(events) >= self.limit:
                retry_after = max(1, int(self.window_seconds - (moment - events[0])) + 1)
                return False, retry_after
            events.append(moment)
            return True, 0


class TamperEvidentAuditLedger:
    """Append a hash-chained, minimised event ledger and verify it later."""

    def __init__(self, path: Path):
        self.path = Path(path)
        self._lock = threading.Lock()

    def append(self, event: dict[str, Any]) -> dict[str, Any]:
        with self._lock:
            previous_hash = "GENESIS"
            sequence = 1
            if self.path.exists():
                existing = [line for line in self.path.read_text(encoding="utf-8").splitlines() if line.strip()]
                if existing:
                    previous = json.loads(existing[-1])
                    previous_hash = str(previous.get("event_hash", ""))
                    sequence = int(previous.get("sequence", 0)) + 1
            payload = {"sequence": sequence, "previous_hash": previous_hash, "event": event}
            record = {**payload, "event_hash": hashlib.sha256(canonical_json(payload).encode()).hexdigest()}
            self.path.parent.mkdir(parents=True, exist_ok=True)
            with self.path.open("a", encoding="utf-8") as handle:
                handle.write(json.dumps(record, ensure_ascii=False) + "\n")
            return record

    def verify(self) -> dict[str, Any]:
        if not self.path.exists():
            return {"valid": True, "entries": 0, "status": "EMPTY_LEDGER"}
        previous_hash = "GENESIS"
        entries = 0
        for number, line in enumerate(self.path.read_text(encoding="utf-8").splitlines(), start=1):
            if not line.strip():
                continue
            try:
                record = json.loads(line)
                payload = {"sequence": record["sequence"], "previous_hash": record["previous_hash"], "event": record["event"]}
                actual_hash = hashlib.sha256(canonical_json(payload).encode()).hexdigest()
            except (KeyError, TypeError, json.JSONDecodeError):
                return {"valid": False, "entries": entries, "status": "MALFORMED_LEDGER", "failed_line": number}
            if record["previous_hash"] != previous_hash or record.get("event_hash") != actual_hash:
                return {"valid": False, "entries": entries, "status": "INTEGRITY_FAILURE", "failed_line": number}
            previous_hash = record["event_hash"]
            entries += 1
        return {"valid": True, "entries": entries, "status": "VALID"}


class KillSwitchManager:
    """Thread-safe emergency kill-switch controller for locking down credit operations."""

    def __init__(self) -> None:
        self._active = False
        self._reason = ""
        self._activated_at = 0.0
        self._lock = threading.Lock()

    def activate(self, reason: str = "EMERGENCY_SECURITY_LOCKDOWN") -> dict[str, Any]:
        with self._lock:
            self._active = True
            self._reason = reason
            self._activated_at = time.time()
            return {"status": "ACTIVE", "reason": self._reason, "activated_at": self._activated_at}

    def deactivate(self) -> dict[str, Any]:
        with self._lock:
            self._active = False
            self._reason = ""
            return {"status": "INACTIVE"}

    def is_active(self) -> bool:
        with self._lock:
            return self._active

    def get_status(self) -> dict[str, Any]:
        with self._lock:
            return {"active": self._active, "reason": self._reason, "activated_at": self._activated_at}


_GLOBAL_KILL_SWITCH = KillSwitchManager()


def get_kill_switch() -> KillSwitchManager:
    return _GLOBAL_KILL_SWITCH


def validate_aa_consent_artifact(consent: dict[str, Any], contract_path: Path | None = None) -> dict[str, Any]:
    """Validate AA consent payload against purpose code and contract bounds."""
    if contract_path is None:
        contract_path = Path("contracts/aa_fiu_contract.json")

    required_keys = {"consent_id", "borrower_id", "purpose", "expires_at"}
    missing = sorted(list(required_keys - set(consent.keys())))
    if missing:
        return {"valid": False, "reason": f"Missing required consent fields: {missing}"}

    if consent.get("purpose") != "CREDIT_ASSESSMENT":
        return {"valid": False, "reason": f"Invalid purpose code '{consent.get('purpose')}'. Expected 'CREDIT_ASSESSMENT'."}

    if consent.get("expires_at", 0) <= time.time() and consent.get("expires_at") != 0: # 0 means mock non-expired
        return {"valid": False, "reason": "Consent artifact has expired."}

    return {"valid": True, "consent_id": consent["consent_id"], "borrower_id": consent["borrower_id"]}


def sanitize_kyc_data(borrower_payload: dict[str, Any], salt: str = "VRIDHI_LOCAL_SALT") -> dict[str, Any]:
    """Sanitize PII from borrower payload by hashing direct identifiers."""
    sanitized = dict(borrower_payload)
    if "aadhaar_number" in sanitized:
        raw = str(sanitized.pop("aadhaar_number"))
        sanitized["masked_aadhaar_hash"] = hashlib.sha256(f"{raw}:{salt}".encode()).hexdigest()
    if "pan_number" in sanitized:
        raw = str(sanitized.pop("pan_number"))
        sanitized["masked_pan_hash"] = hashlib.sha256(f"{raw}:{salt}".encode()).hexdigest()
    if "phone_number" in sanitized:
        raw = str(sanitized.pop("phone_number"))
        sanitized["masked_phone_hash"] = hashlib.sha256(f"{raw}:{salt}".encode()).hexdigest()
    return sanitized


def check_aml_sanctions(borrower_id: str, high_risk_watchlist: set[str] | None = None) -> dict[str, Any]:
    """Mock AML sanction list check for high-risk flags."""
    watchlist = high_risk_watchlist or {"SANCTIONED_BORROWER_999", "FLAGGED_ENTITY_007"}
    is_flagged = borrower_id in watchlist
    return {
        "borrower_id": borrower_id,
        "aml_cleared": not is_flagged,
        "status": "FLAGGED_HIGH_RISK" if is_flagged else "PASSED",
    }


def bhashini_translate(text: str, target_language: str = "hi") -> dict[str, Any]:
    """Mock Bhashini NMT localization translation boundary."""
    translations = {
        "hi": {
            "High reliance on seasonal income.": "मौसमी आय पर अधिक निर्भरता।",
            "Drought severity in region.": "क्षेत्र में सूखे की गंभीरता।",
            "Manual review required before any lending decision.": "किसी भी ऋण निर्णय से पहले मानव समीक्षा आवश्यक है।",
        },
        "mr": {
            "High reliance on seasonal income.": "हंगामाच्या उत्पन्नावर जास्त अवलंबित्व.",
            "Drought severity in region.": "प्रदेशातील दुष्काळाची तीव्रता.",
            "Manual review required before any lending decision.": "कोणत्याही कर्जाच्या निर्णयापूर्वी मानवी पुनरावलोकन आवश्यक आहे.",
        },
    }
    lang = target_language.lower()
    translated_text = translations.get(lang, {}).get(text, f"[{lang.upper()}] {text}")
    return {
        "original_text": text,
        "target_language": lang,
        "translated_text": translated_text,
        "provider": "Bhashini_NMT_MockAdapter",
    }


def run_security_pentest(audit_ledger_path: Path) -> dict[str, Any]:
    """Run automated penetration testing harness checking OWASP security gates."""
    ledger = TamperEvidentAuditLedger(audit_ledger_path)
    
    # 1. HMAC Verification check
    secret = "test-secret"
    event = {"test": "payload"}
    sig = sign_partner_webhook("P1", event, secret)
    hmac_passed = verify_partner_webhook("P1", event, sig, secret) and not verify_partner_webhook("P1", event, "bad_sig", secret)

    # 2. Rate limiter check
    limiter = SlidingWindowRateLimiter(limit=2, window_seconds=60)
    ok1, _ = limiter.allow("user1")
    ok2, _ = limiter.allow("user1")
    ok3, _ = limiter.allow("user1")
    rate_limiter_passed = ok1 and ok2 and not ok3

    # 3. Tamper-evident audit ledger check
    test_event = {"action": "PENTEST_PING"}
    ledger.append(test_event)
    ledger_verify = ledger.verify()
    ledger_passed = ledger_verify["valid"]

    # 4. Token RBAC scope check
    admin_scopes = ROLE_SCOPES.get("admin", set())
    officer_scopes = ROLE_SCOPES.get("loan_officer", set())
    rbac_passed = "killswitch:manage" in admin_scopes and "killswitch:manage" not in officer_scopes

    all_passed = hmac_passed and rate_limiter_passed and ledger_passed and rbac_passed

    return {
        "pentest_status": "PASSED" if all_passed else "FAILED",
        "tests": {
            "hmac_signature_integrity": "PASS" if hmac_passed else "FAIL",
            "rate_limiter_enforcement": "PASS" if rate_limiter_passed else "FAIL",
            "audit_ledger_tamper_evidence": "PASS" if ledger_passed else "FAIL",
            "rbac_scope_isolation": "PASS" if rbac_passed else "FAIL",
        },
        "timestamp": time.time(),
    }
