"""Phase 3 FastAPI sandbox for consent-bound synthetic risk workflows."""

from __future__ import annotations

import base64
import hashlib
import json
import os
import sqlite3
import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any, Protocol
from urllib.parse import parse_qs

from cryptography.fernet import Fernet, InvalidToken
from fastapi import Depends, FastAPI, Header, HTTPException, Request, status
from fastapi.responses import JSONResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from .risk_engine import FEATURE_COLUMNS, RiskEngine
from .policy import audit_record, evaluate_manual_review, load_policy_contract
from .security import DEFAULT_CLIENT_ROLES, ROLE_SCOPES, SlidingWindowRateLimiter, TamperEvidentAuditLedger, verify_partner_webhook, get_kill_switch, bhashini_translate
from .bank_router import bank_router


DEMO_KEY = base64.urlsafe_b64encode(hashlib.sha256(b"vridhi-local-sandbox-never-production").digest()).decode()


@dataclass(frozen=True)
class SandboxSettings:
    token_key: str = DEMO_KEY
    payload_key: str = DEMO_KEY
    client_id: str = "sandbox-client"
    client_secret: str = "sandbox-secret"
    consent_db: Path = Path("runtime/consents.sqlite3")
    model_dir: Path = Path("artifacts/risk/reference")
    policy_audit_path: Path = Path("runtime/policy_score_audit.jsonl")
    policy_artifact_dir: Path = Path("artifacts/policy/reference")
    security_audit_path: Path = Path("runtime/security_audit.jsonl")
    partner_webhook_secret: str = "sandbox-partner-secret-never-production"
    rate_limit_requests: int = 120
    rate_limit_window_seconds: int = 60
    client_roles: dict[str, str] = field(default_factory=lambda: dict(DEFAULT_CLIENT_ROLES))
    redis_url: str | None = None

    @classmethod
    def from_env(cls) -> "SandboxSettings":
        return cls(
            token_key=os.getenv("VRIDHI_SANDBOX_TOKEN_KEY", DEMO_KEY),
            payload_key=os.getenv("VRIDHI_SANDBOX_PAYLOAD_KEY", DEMO_KEY),
            client_id=os.getenv("VRIDHI_SANDBOX_CLIENT_ID", "sandbox-client"),
            client_secret=os.getenv("VRIDHI_SANDBOX_CLIENT_SECRET", "sandbox-secret"),
            consent_db=Path(os.getenv("VRIDHI_CONSENT_DB", "runtime/consents.sqlite3")),
            model_dir=Path(os.getenv("VRIDHI_RISK_MODEL_DIR", "artifacts/risk/reference")),
            policy_audit_path=Path(os.getenv("VRIDHI_POLICY_AUDIT_PATH", "runtime/policy_score_audit.jsonl")),
            policy_artifact_dir=Path(os.getenv("VRIDHI_POLICY_ARTIFACT_DIR", "artifacts/policy/reference")),
            security_audit_path=Path(os.getenv("VRIDHI_SECURITY_AUDIT_PATH", "runtime/security_audit.jsonl")),
            partner_webhook_secret=os.getenv("VRIDHI_PARTNER_WEBHOOK_SECRET", "sandbox-partner-secret-never-production"),
            rate_limit_requests=int(os.getenv("VRIDHI_RATE_LIMIT_REQUESTS", "120")),
            rate_limit_window_seconds=int(os.getenv("VRIDHI_RATE_LIMIT_WINDOW_SECONDS", "60")),
            redis_url=os.getenv("REDIS_URL"),
        )


def get_borrower_catalog(settings: SandboxSettings) -> list[dict[str, Any]]:
    csv_file = Path("data/loan_applications_faculty_demo.csv")
    borrowers = []

    if csv_file.exists():
        import csv
        try:
            with csv_file.open("r", encoding="utf-8") as f:
                reader = csv.DictReader(f)
                for row in reader:
                    score = int(float(row.get("synthetic_credit_score", 650)))
                    pd_pct = row.get("risk_pd_pct", "15.0%")
                    pd_raw = float(pd_pct.replace("%", "")) / 100.0 if "%" in pd_pct else float(pd_pct)
                    band = row.get("risk_band", "Low").capitalize()
                    if band in ("Medium", "Moderate"):
                        band = "Moderate"

                    # Generate score explanation reasons based on financial & payment behavioral indicators
                    income = float(row.get("monthly_income_inr", 35000))
                    expense = float(row.get("monthly_expense_inr", 22000))
                    cash = float(row.get("cash_balance_inr", 10000))
                    missed = int(float(row.get("missed_utility_bills", 0)))
                    drought = float(row.get("drought_severity", 0.2))

                    on_time_str = row.get("on_time_payment_pct_24m", "95%")
                    on_time_num = float(on_time_str.replace("%", "")) if "%" in on_time_str else 95.0
                    bounces = int(float(row.get("nach_bounces_12m", 0)))

                    reasons = []
                    if on_time_num < 85.0:
                        reasons.append({"feature": "24-Month repayment delinquency trail", "direction": "increases_risk", "pts": f"+{int((100-on_time_num)*1.2)} risk pts", "width": f"{min(95, int((100-on_time_num)*2.5))}%", "color": "rose"})
                    if bounces > 0:
                        reasons.append({"feature": "NACH mandate bounces (12M)", "direction": "increases_risk", "pts": f"+{bounces*38} risk pts", "width": f"{min(90, bounces*45)}%", "color": "rose"})
                    if drought > 0.4:
                        reasons.append({"feature": "Regional economic & climate stress", "direction": "increases_risk", "pts": f"+{int(drought*80)} risk pts", "width": f"{min(95, int(drought*100))}%", "color": "rose"})
                    if missed > 0:
                        reasons.append({"feature": "Delayed commercial utility bills", "direction": "increases_risk", "pts": f"+{missed*20} risk pts", "width": f"{min(80, missed*35)}%", "color": "rose"})
                    if income < expense:
                        reasons.append({"feature": "Operating cashflow deficit", "direction": "increases_risk", "pts": "+45 risk pts", "width": "85%", "color": "rose"})
                    if on_time_num >= 90.0:
                        reasons.append({"feature": "High 24M payment punctuality trail", "direction": "decreases_risk", "pts": "-28 risk pts", "width": "60%", "color": "emerald"})
                    if cash > 15000:
                        reasons.append({"feature": "Healthy working capital reserve", "direction": "decreases_risk", "pts": "-25 risk pts", "width": "55%", "color": "emerald"})
                    if not reasons:
                        reasons = [
                            {"feature": "Stable trade revenue & turnover", "direction": "decreases_risk", "pts": "-18 risk pts", "width": "40%", "color": "emerald"},
                            {"feature": "Consistent supplier network coverage", "direction": "decreases_risk", "pts": "-12 risk pts", "width": "30%", "color": "emerald"}
                        ]

                    enterprise = row.get("enterprise_type") or row.get("crop_type", "Rural Enterprise")

                    borrowers.append({
                        "id": row.get("application_id", f"APP-{row.get('account_number', '000')}"),
                        "farmer_id": f"entrepreneur:{row.get('pincode', '413001')}:{row.get('account_number', '001')[-3:]}",
                        "account_no": row.get("account_number", ""),
                        "bank_name": row.get("bank_name", ""),
                        "branch_name": row.get("branch_name", ""),
                        "ifsc_code": row.get("ifsc_code", ""),
                        "name": row.get("borrower_name", ""),
                        "village": row.get("branch_name", ""),
                        "crop": enterprise,
                        "enterprise_type": enterprise,
                        "pincode": row.get("pincode", ""),
                        "on_time_payment_pct_24m": row.get("on_time_payment_pct_24m", "95%"),
                        "dpd_trail_12m": row.get("dpd_trail_12m", "0-0-0-0-0-0-0-0-0-0-0-0"),
                        "nach_bounces_12m": bounces,
                        "avg_payment_delay_days": row.get("avg_payment_delay_days", "0.0"),
                        "bbps_utility_compliance_pct": row.get("bbps_utility_compliance_pct", "96%"),
                        "credit_utilization_pct": row.get("credit_utilization_pct", "32%"),
                        "score": score,
                        "pd": pd_pct,
                        "pd_raw": pd_raw,
                        "band": band,
                        "reasons": reasons,
                        "recommended_step": row.get("recommended_action", "Request updated business receipts and discuss working capital repayment plan."),
                        "policy_decision": row.get("policy_decision", "MANUAL_REVIEW_REQUIRED")
                    })
            if borrowers:
                return borrowers
        except Exception:
            pass


    # Fallback to research_scores if CSV not present
    scores_path = settings.model_dir / "research_scores.csv"
    if scores_path.exists():
        import csv
        try:
            with scores_path.open("r", encoding="utf-8") as f:
                reader = csv.DictReader(f)
                for idx, row in enumerate(list(reader)[:50]):
                    f_id = row.get("farmer_id", f"farmer:413001:{idx+1:03d}")
                    clean_id = f_id.replace("farmer:", "F-")
                    score = int(float(row.get("synthetic_score_300_900", 650)))
                    pd_val = float(row.get("risk_pd", 0.15))
                    band = "Low" if pd_val < 0.15 else ("Moderate" if pd_val < 0.30 else "High")
                    borrowers.append({
                        "id": clean_id,
                        "farmer_id": f_id,
                        "account_no": f"ACC-{clean_id.replace('F-', '')}",
                        "bank_name": "State Bank of India",
                        "branch_name": "Regional Agri Branch",
                        "ifsc_code": "SBIN0001234",
                        "name": f"Farmer {idx+1}",
                        "village": "Rural Maharashtra",
                        "crop": "Cotton",
                        "pincode": "413001",
                        "score": score,
                        "pd": f"{pd_val * 100:.1f}%",
                        "pd_raw": pd_val,
                        "band": band,
                        "reasons": [{"feature": "Crop income pressure", "direction": "increases_risk", "pts": "+20 risk pts", "width": "50%", "color": "rose"}],
                        "recommended_step": "Request updated crop evidence before loan renewal."
                    })
            return borrowers
        except Exception:
            pass

    return borrowers


class ConsentRequest(BaseModel):
    purpose: str = Field(pattern="^credit_underwriting$")
    data_types: list[str] = Field(min_length=1)
    expires_in_minutes: int = Field(default=30, ge=1, le=1_440)


class EncryptedEnvelope(BaseModel):
    consent_id: str
    ciphertext: str = Field(min_length=20)
    idempotency_key: str = Field(min_length=8, max_length=128)


class FinancialPayload(BaseModel):
    farmer_id: str = Field(pattern=r"^farmer:\d{6}:\d{3}$")
    month: str = Field(pattern=r"^\d{4}-\d{2}-\d{2}$")
    cash_balance: float
    income_inr: float
    expense_inr: float
    net_cash_flow_inr: float
    income_volatility_3m: float = Field(ge=0)
    missed_utility_payments: int = Field(ge=0)
    overdue_installments: int = Field(ge=0)
    drought_severity: float = Field(ge=0, le=1)
    repayment_ability_proxy: float = Field(ge=0)
    buyer_network_stress: float = Field(ge=0, le=1)
    buyer_network_coverage: float = Field(ge=0, le=1)


class UPIEventPayload(BaseModel):
    event_id: str = Field(min_length=8, max_length=128)
    timestamp: str
    source_id: str
    target_id: str
    amount_inr: float = Field(gt=0)
    transaction_type: str


class PartnerWebhookEvent(BaseModel):
    event_id: str = Field(min_length=8, max_length=128)
    event_type: str = Field(pattern=r"^(consent_status|synthetic_data_ready|deletion_confirmed)$")
    occurred_at: str = Field(pattern=r"^\d{4}-\d{2}-\d{2}T.*Z$")
    payload_digest: str = Field(pattern=r"^[a-f0-9]{64}$")
    data_classification: str = Field(pattern=r"^synthetic$")


class RetentionRunRequest(BaseModel):
    idempotency_retention_hours: int = Field(default=24, ge=1, le=24 * 365)


class BhashiniTranslationRequest(BaseModel):
    text: str = Field(min_length=1)
    target_language: str = Field(default="hi", pattern="^(hi|mr|en)$")


class LoanApplicationFormInput(BaseModel):
    borrower_name: str = Field(min_length=2)
    bank_name: str = Field(min_length=2)
    branch_name: str = Field(min_length=2)
    account_number: str = Field(min_length=4)
    ifsc_code: str = Field(min_length=4)
    pincode: int = Field(ge=100000, le=999999)
    crop_type: str = Field(min_length=2)
    monthly_income_inr: float = Field(ge=0)
    monthly_expense_inr: float = Field(ge=0)
    cash_balance_inr: float = Field(ge=0)
    missed_utility_bills: int = Field(default=0, ge=0)
    overdue_installments: int = Field(default=0, ge=0)
    drought_severity: float = Field(default=0.2, ge=0.0, le=1.0)
    is_agri: str = Field(default="no")
    land_acres: float = Field(default=0.0, ge=0)
    irrigation_type: str = Field(default="")
    business_vintage_years: int = Field(default=3, ge=0)
    premises_status: str = Field(default="")


class KillSwitchRequest(BaseModel):
    action: str = Field(pattern="^(ACTIVATE|DEACTIVATE)$")
    reason: str = Field(default="EMERGENCY_ADMIN_LOCKDOWN")


class ConsentStore:
    def __init__(self, path: Path):
        path.parent.mkdir(parents=True, exist_ok=True)
        self.connection = sqlite3.connect(path, check_same_thread=False)
        self.connection.execute("CREATE TABLE IF NOT EXISTS consents (id TEXT PRIMARY KEY, subject TEXT, purpose TEXT, data_types TEXT, expires_at TEXT, status TEXT)")
        self.connection.execute("CREATE TABLE IF NOT EXISTS idempotency (key TEXT PRIMARY KEY, created_at TEXT)")
        self.connection.commit()

    def create(self, subject: str, request: ConsentRequest) -> dict[str, Any]:
        consent_id = f"consent-{uuid.uuid4()}"
        expires_at = datetime.now(UTC) + timedelta(minutes=request.expires_in_minutes)
        self.connection.execute("INSERT INTO consents VALUES (?, ?, ?, ?, ?, ?)", (consent_id, subject, request.purpose, json.dumps(sorted(request.data_types)), expires_at.isoformat(), "ACTIVE"))
        self.connection.commit()
        return {"consent_id": consent_id, "purpose": request.purpose, "data_types": request.data_types, "expires_at": expires_at.isoformat(), "status": "ACTIVE"}

    def validate(self, consent_id: str, subject: str, required_data_type: str) -> None:
        row = self.connection.execute("SELECT subject, purpose, data_types, expires_at, status FROM consents WHERE id = ?", (consent_id,)).fetchone()
        if row is None or row[0] != subject or row[4] != "ACTIVE" or datetime.fromisoformat(row[3]) <= datetime.now(UTC):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Consent is absent, expired, revoked, or belongs to another client.")
        if row[1] != "credit_underwriting" or required_data_type not in json.loads(row[2]):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Consent does not cover this purpose or data type.")

    def revoke(self, consent_id: str, subject: str) -> None:
        cursor = self.connection.execute("UPDATE consents SET status = 'REVOKED' WHERE id = ? AND subject = ?", (consent_id, subject))
        self.connection.commit()
        if not cursor.rowcount:
            raise HTTPException(status_code=404, detail="Consent not found.")

    def claim_idempotency_key(self, key: str) -> None:
        try:
            self.connection.execute("INSERT INTO idempotency VALUES (?, ?)", (key, datetime.now(UTC).isoformat()))
            self.connection.commit()
        except sqlite3.IntegrityError as error:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Duplicate idempotency key.") from error

    def run_retention(self, idempotency_retention_hours: int) -> dict[str, int]:
        """Delete expired synthetic consent metadata only when an admin invokes this control."""
        now = datetime.now(UTC)
        consent_cursor = self.connection.execute("DELETE FROM consents WHERE expires_at <= ?", (now.isoformat(),))
        cutoff = (now - timedelta(hours=idempotency_retention_hours)).isoformat()
        key_cursor = self.connection.execute("DELETE FROM idempotency WHERE created_at <= ?", (cutoff,))
        self.connection.commit()
        return {"expired_consents_deleted": max(consent_cursor.rowcount, 0), "expired_idempotency_keys_deleted": max(key_cursor.rowcount, 0)}


class PolicyAuditStore:
    """Append minimised sandbox policy events without financial payloads."""

    def __init__(self, path: Path):
        self.path = path

    def record(self, event: dict[str, Any]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(event) + "\n")


class StreamBus(Protocol):
    async def publish(self, stream: str, event: dict[str, str]) -> str: ...
    async def recent(self, stream: str, count: int) -> list[dict[str, str]]: ...


class InMemoryStreamBus:
    def __init__(self):
        self.events: dict[str, list[dict[str, str]]] = {}

    async def publish(self, stream: str, event: dict[str, str]) -> str:
        event = {**event, "stream_id": f"mem-{len(self.events.get(stream, [])) + 1}"}
        self.events.setdefault(stream, []).append(event)
        return event["stream_id"]

    async def recent(self, stream: str, count: int) -> list[dict[str, str]]:
        return list(reversed(self.events.get(stream, [])[-count:]))


class RedisStreamBus:
    def __init__(self, redis_url: str):
        from redis.asyncio import Redis
        self.client = Redis.from_url(redis_url, decode_responses=True)

    async def publish(self, stream: str, event: dict[str, str]) -> str:
        return str(await self.client.xadd(stream, event))

    async def recent(self, stream: str, count: int) -> list[dict[str, str]]:
        rows = await self.client.xrevrange(stream, count=count)
        return [{"stream_id": str(entry_id), **{str(key): str(value) for key, value in fields.items()}} for entry_id, fields in rows]


def _token(settings: SandboxSettings, subject: str, role: str, scopes: list[str]) -> str:
    payload = {"sub": subject, "role": role, "scopes": sorted(set(scopes)), "exp": int((datetime.now(UTC) + timedelta(minutes=15)).timestamp())}
    return Fernet(settings.token_key.encode()).encrypt(json.dumps(payload).encode()).decode()


def _identity(settings: SandboxSettings, authorization: str | None, required_scope: str, allowed_roles: set[str] | None = None) -> dict[str, Any]:
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Bearer token required.")
    try:
        token = json.loads(Fernet(settings.token_key.encode()).decrypt(authorization[7:].encode()).decode())
    except (InvalidToken, json.JSONDecodeError) as error:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid access token.") from error
    if token["exp"] <= int(datetime.now(UTC).timestamp()) or required_scope not in token["scopes"]:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access token is expired or lacks required scope.")
    if allowed_roles is not None and token.get("role") not in allowed_roles:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access token role is not authorised for this sandbox action.")
    return token


def create_app(settings: SandboxSettings | None = None, engine: RiskEngine | None = None, stream_bus: StreamBus | None = None) -> FastAPI:
    settings = settings or SandboxSettings.from_env()
    store = ConsentStore(settings.consent_db)
    policy_audits = PolicyAuditStore(settings.policy_audit_path)
    security_ledger = TamperEvidentAuditLedger(settings.security_audit_path)
    rate_limiter = SlidingWindowRateLimiter(settings.rate_limit_requests, settings.rate_limit_window_seconds)
    cipher = Fernet(settings.payload_key.encode())
    if engine is None and (settings.model_dir / "risk_engine.joblib").exists():
        engine = RiskEngine.load(settings.model_dir)
    bus: StreamBus = stream_bus or (RedisStreamBus(settings.redis_url) if settings.redis_url else InMemoryStreamBus())
    app = FastAPI(title="Vridhi AA-Compatible Sandbox", version="0.1.0")
    app.include_router(bank_router)

    app.state.settings, app.state.consent_store, app.state.stream_bus, app.state.risk_engine, app.state.policy_audits, app.state.security_ledger = settings, store, bus, engine, policy_audits, security_ledger

    @app.middleware("http")
    async def apply_rate_limit(request: Request, call_next):
        if request.url.path.startswith("/v1/"):
            client_key = request.client.host if request.client else "unknown"
            allowed, retry_after = rate_limiter.allow(client_key)
            if not allowed:
                return JSONResponse(status_code=429, content={"detail": "Sandbox rate limit exceeded. Retry later."}, headers={"Retry-After": str(retry_after)})
        response = await call_next(request)
        response.headers["X-RateLimit-Limit"] = str(settings.rate_limit_requests)
        return response

    def guard(scope: str, roles: set[str] | None = None):
        def dependency(authorization: str | None = Header(default=None)) -> dict[str, Any]:
            return _identity(settings, authorization, scope, roles)
        return dependency

    def decrypt(envelope: EncryptedEnvelope, subject: str, type_: str, schema: type[BaseModel]) -> BaseModel:
        store.validate(envelope.consent_id, subject, type_)
        store.claim_idempotency_key(envelope.idempotency_key)
        try:
            return schema.model_validate_json(cipher.decrypt(envelope.ciphertext.encode()))
        except (InvalidToken, ValueError) as error:
            raise HTTPException(status_code=422, detail="Payload is not a valid encrypted sandbox envelope.") from error

    @app.get("/health")
    async def health() -> dict[str, Any]:
        return {"status": "ok", "sandbox": True, "model_loaded": app.state.risk_engine is not None, "stream_backend": type(bus).__name__}

    @app.get("/v1/policy/reference-summary")
    async def policy_reference_summary() -> dict[str, Any]:
        """Expose only aggregate synthetic policy diagnostics for the lender UI."""
        contract = load_policy_contract()
        report_path = settings.policy_artifact_dir / "fairness_diagnostic.json"
        report: dict[str, Any] = {}
        if report_path.exists():
            try:
                report = json.loads(report_path.read_text(encoding="utf-8"))
            except json.JSONDecodeError:
                report = {}
        return {
            "sandbox": True,
            "data_classification": "synthetic",
            "policy_id": contract["policy_id"],
            "policy_version": contract["version"],
            "manual_review_only": True,
            "automatic_approval": False,
            "automatic_decline": False,
            "artifact_status": "AVAILABLE" if report else "NOT_GENERATED",
            "manual_review_records": report.get("overall", {}).get("records", 0),
            "fairness_status": report.get("overall_status", "NOT_GENERATED"),
            "cohorts": report.get("cohorts", {}),
            "fairness_note": report.get("fairness_claim", "Run the Phase 7 policy command to generate synthetic diagnostics."),
        }

    @app.get("/v1/security/sandbox-summary")
    async def security_sandbox_summary() -> dict[str, Any]:
        """Return a safe dashboard summary; no secrets, tokens, or raw audit events."""
        return {
            "sandbox": True,
            "data_classification": "synthetic",
            "live_partner_connections": False,
            "roles": sorted(set(settings.client_roles.values())),
            "role_scopes": {role: sorted(scopes) for role, scopes in ROLE_SCOPES.items()},
            "signed_partner_webhooks": "SIMULATED_ONLY",
            "rate_limit": {"requests": settings.rate_limit_requests, "window_seconds": settings.rate_limit_window_seconds},
            "audit_ledger": security_ledger.verify(),
            "retention": "ADMIN_TRIGGERED_EXPIRED_SYNTHETIC_METADATA_ONLY",
        }

    @app.post("/v1/oauth/token")
    async def issue_token(request: Request) -> dict[str, Any]:
        body = parse_qs((await request.body()).decode())
        client_id, client_secret = body.get("client_id", [""])[0], body.get("client_secret", [""])[0]
        scopes = body.get("scope", [""])[0].split()
        role = settings.client_roles.get(client_id)
        if body.get("grant_type", [""])[0] != "client_credentials" or role is None or client_secret != settings.client_secret:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid sandbox client credentials.")
        if not set(scopes).issubset(ROLE_SCOPES[role]):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Requested scope is not permitted for this sandbox role.")
        security_ledger.append({"event_type": "token_issued", "timestamp": datetime.now(UTC).isoformat(), "client_id": client_id, "role": role, "scopes": sorted(scopes), "contains_raw_financial_payload": False})
        return {"access_token": _token(settings, client_id, role, scopes), "token_type": "Bearer", "expires_in": 900, "scope": " ".join(scopes), "sandbox_role": role}

    @app.post("/v1/consents", status_code=status.HTTP_201_CREATED)
    async def create_consent(request: ConsentRequest, identity: dict[str, Any] = Depends(guard("consent:write", {"loan_officer"}))) -> dict[str, Any]:
        result = store.create(identity["sub"], request)
        security_ledger.append({"event_type": "consent_created", "timestamp": datetime.now(UTC).isoformat(), "actor": identity["sub"], "role": identity["role"], "contains_raw_financial_payload": False})
        return result

    @app.delete("/v1/consents/{consent_id}", status_code=status.HTTP_204_NO_CONTENT)
    async def revoke_consent(consent_id: str, identity: dict[str, Any] = Depends(guard("consent:write", {"loan_officer"}))) -> None:
        store.revoke(consent_id, identity["sub"])
        security_ledger.append({"event_type": "consent_revoked", "timestamp": datetime.now(UTC).isoformat(), "actor": identity["sub"], "role": identity["role"], "contains_raw_financial_payload": False})

    @app.post("/v1/scores")
    async def score(envelope: EncryptedEnvelope, identity: dict[str, Any] = Depends(guard("score:write", {"loan_officer", "reviewer"}))) -> dict[str, Any]:
        ks = get_kill_switch()
        if ks.is_active():
            raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=f"EMERGENCY_KILL_SWITCH_ACTIVE: {ks.get_status()['reason']}")
        payload = decrypt(envelope, identity["sub"], "financial_information", FinancialPayload)
        if app.state.risk_engine is None:
            raise HTTPException(status_code=503, detail="Risk model artifact is unavailable.")
        row = payload.model_dump()
        if set(FEATURE_COLUMNS) - set(row):
            raise HTTPException(status_code=422, detail="Financial payload lacks approved risk features.")
        result = app.state.risk_engine.score([row])[0]
        policy = evaluate_manual_review(result)
        policy_audits.record(audit_record(result, policy, identity["sub"]))
        security_ledger.append({"event_type": "score_manual_review_created", "timestamp": datetime.now(UTC).isoformat(), "actor": identity["sub"], "role": identity["role"], "policy_version": policy["policy_version"], "contains_raw_financial_payload": False})
        stream_id = await bus.publish("risk-score-events", {"event_id": envelope.idempotency_key, "consent_id": envelope.consent_id, "timestamp": datetime.now(UTC).isoformat(), "risk_pd": str(result["risk_pd"])})
        return {**result, "policy": policy, "stream_id": stream_id, "consent_id": envelope.consent_id, "sandbox": True}

    @app.post("/v1/upi-events", status_code=status.HTTP_202_ACCEPTED)
    async def ingest_upi(envelope: EncryptedEnvelope, identity: dict[str, Any] = Depends(guard("stream:write", {"loan_officer"}))) -> dict[str, Any]:
        payload = decrypt(envelope, identity["sub"], "upi_transaction", UPIEventPayload)
        digest = hashlib.sha256(envelope.ciphertext.encode()).hexdigest()
        stream_id = await bus.publish("upi-transactions", {"event_id": payload.event_id, "consent_id": envelope.consent_id, "timestamp": payload.timestamp, "ciphertext_sha256": digest})
        security_ledger.append({"event_type": "synthetic_upi_event_ingested", "timestamp": datetime.now(UTC).isoformat(), "actor": identity["sub"], "role": identity["role"], "contains_raw_financial_payload": False})
        return {"accepted": True, "stream_id": stream_id, "event_id": payload.event_id, "sandbox": True}

    @app.post("/v1/partner-webhooks/{partner_id}", status_code=status.HTTP_202_ACCEPTED)
    async def ingest_partner_webhook(
        partner_id: str,
        event: PartnerWebhookEvent,
        x_vridhi_signature: str | None = Header(default=None),
        identity: dict[str, Any] = Depends(guard("partner:webhook", {"admin"})),
    ) -> dict[str, Any]:
        if partner_id not in {"sandbox-lender", "sandbox-fiu"}:
            raise HTTPException(status_code=404, detail="Unknown synthetic partner.")
        payload = event.model_dump()
        if not verify_partner_webhook(partner_id, payload, x_vridhi_signature, settings.partner_webhook_secret):
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Partner webhook signature is invalid.")
        store.claim_idempotency_key(f"partner:{partner_id}:{event.event_id}")
        stream_id = await bus.publish("partner-webhooks", {"event_id": event.event_id, "partner_id": partner_id, "event_type": event.event_type, "timestamp": event.occurred_at, "payload_digest": event.payload_digest})
        security_ledger.append({"event_type": "signed_synthetic_partner_webhook_accepted", "timestamp": datetime.now(UTC).isoformat(), "actor": identity["sub"], "role": identity["role"], "partner_id": partner_id, "partner_event_type": event.event_type, "contains_raw_financial_payload": False})
        return {"accepted": True, "signature_verified": True, "stream_id": stream_id, "sandbox": True, "data_classification": "synthetic"}

    @app.get("/v1/admin/audit-integrity")
    async def audit_integrity(identity: dict[str, Any] = Depends(guard("audit:read", {"admin"}))) -> dict[str, Any]:
        return {**security_ledger.verify(), "sandbox": True, "requested_by_role": identity["role"]}

    @app.post("/v1/admin/retention/run")
    async def run_retention(request: RetentionRunRequest, identity: dict[str, Any] = Depends(guard("retention:run", {"admin"}))) -> dict[str, Any]:
        result = store.run_retention(request.idempotency_retention_hours)
        security_ledger.append({"event_type": "synthetic_retention_run", "timestamp": datetime.now(UTC).isoformat(), "actor": identity["sub"], "role": identity["role"], "retention_hours": request.idempotency_retention_hours, "contains_raw_financial_payload": False})
        return {**result, "sandbox": True, "automatic_deletion": False, "note": "This admin-triggered sandbox job purged expired synthetic metadata only."}

    @app.post("/v1/admin/kill-switch")
    async def toggle_kill_switch(request: KillSwitchRequest, identity: dict[str, Any] = Depends(guard("killswitch:manage", {"admin"}))) -> dict[str, Any]:
        ks = get_kill_switch()
        if request.action == "ACTIVATE":
            res = ks.activate(request.reason)
            security_ledger.append({"event_type": "kill_switch_activated", "timestamp": datetime.now(UTC).isoformat(), "actor": identity["sub"], "reason": request.reason})
        else:
            res = ks.deactivate()
            security_ledger.append({"event_type": "kill_switch_deactivated", "timestamp": datetime.now(UTC).isoformat(), "actor": identity["sub"]})
        return {**res, "sandbox": True}

    @app.get("/v1/admin/kill-switch")
    async def kill_switch_status(identity: dict[str, Any] = Depends(guard("audit:read", {"admin", "reviewer"}))) -> dict[str, Any]:
        return {**get_kill_switch().get_status(), "sandbox": True}

    @app.post("/v1/bhashini/translate")
    async def translate_text(request: BhashiniTranslationRequest, identity: dict[str, Any] = Depends(guard("stream:read", {"loan_officer", "reviewer", "admin"}))) -> dict[str, Any]:
        return bhashini_translate(request.text, request.target_language)

    @app.get("/v1/streams/{stream_name}/recent")
    async def recent_events(stream_name: str, count: int = 10, identity: dict[str, Any] = Depends(guard("stream:read", {"loan_officer", "reviewer", "admin"}))) -> dict[str, Any]:
        if stream_name not in {"upi-transactions", "risk-score-events", "partner-webhooks"}:
            raise HTTPException(status_code=404, detail="Unknown sandbox stream.")
        return {"stream": stream_name, "events": await bus.recent(stream_name, min(max(count, 1), 100)), "sandbox": True}

    @app.get("/v1/rollout/status")
    async def rollout_status() -> dict[str, Any]:
        from .rollout import ProductionRolloutManager
        mgr = ProductionRolloutManager()
        return mgr.evaluate_health_and_rollback()

    @app.get("/v1/borrowers")
    async def list_borrowers(q: str | None = None) -> dict[str, Any]:
        catalog = get_borrower_catalog(settings)
        if q:
            query = q.strip().lower()
            catalog = [
                b for b in catalog
                if query in b["name"].lower()
                or query in b["id"].lower()
                or query in b["account_no"].lower()
                or query in b["farmer_id"].lower()
                or query in b["village"].lower()
                or query in b["crop"].lower()
                or query in str(b["pincode"])
            ]
        return {"count": len(catalog), "borrowers": catalog, "sandbox": True}

    @app.get("/v1/borrowers/{borrower_id}")
    async def get_borrower(borrower_id: str) -> dict[str, Any]:
        catalog = get_borrower_catalog(settings)
        clean = borrower_id.strip().lower()
        for b in catalog:
            if b["id"].lower() == clean or b["farmer_id"].lower() == clean or b["account_no"].lower() == clean:
                return b
        raise HTTPException(status_code=404, detail=f"Borrower '{borrower_id}' not found in review catalog.")

    @app.post("/v1/applications", status_code=status.HTTP_201_CREATED)
    async def create_loan_application(form: LoanApplicationFormInput) -> dict[str, Any]:
        csv_file = Path("data/loan_applications_faculty_demo.csv")
        import csv

        # Count existing applications for app_id
        count = 1
        if csv_file.exists():
            with csv_file.open("r", encoding="utf-8") as f:
                count = sum(1 for _ in f)

        app_id = f"APP-2026-{count:03d}"
        now_iso = datetime.now(UTC).isoformat()

        # Risk scoring calculation
        income = max(1.0, form.monthly_income_inr)
        expense = form.monthly_expense_inr
        cash = form.cash_balance_inr
        drought = form.drought_severity
        missed = form.missed_utility_bills
        overdue = form.overdue_installments

        is_agri = form.is_agri == "yes"
        agri_bonus = -0.05 if (is_agri and "Solar" in form.irrigation_type) or (is_agri and "Drip" in form.irrigation_type) else 0.0
        vintage_bonus = -0.04 if (not is_agri and form.business_vintage_years >= 3) else 0.0

        pd_raw = max(0.02, min(0.95, 0.05 + (drought * 0.35) + (missed * 0.08) + (overdue * 0.12) - (cash / max(1000.0, income * 2.0)) * 0.08 + agri_bonus + vintage_bonus))
        score = max(300, min(900, int(850 - pd_raw * 600)))
        risk_pd_pct = f"{pd_raw * 100:.1f}%"
        risk_band = "Low" if pd_raw < 0.15 else ("Moderate" if pd_raw < 0.30 else "High")

        if risk_band == "High":
            rec_step = "High regional economic/credit stress detected. Conduct mandatory underwriter review before credit renewal."
        elif risk_band == "Moderate":
            rec_step = "Conduct in-person business check to verify GST/trade receipts and inventory turnover."
        else:
            rec_step = "Standard review approved. Proceed to document verification and credit disbursal."

        new_row = {
            "application_id": app_id,
            "timestamp": now_iso,
            "bank_name": form.bank_name,
            "branch_name": form.branch_name,
            "account_number": form.account_number,
            "ifsc_code": form.ifsc_code,
            "borrower_name": form.borrower_name,
            "pincode": str(form.pincode),
            "is_agri_enterprise": form.is_agri,
            "enterprise_sector": "Agricultural / Farming" if is_agri else "Non-Agri Micro-Enterprise",
            "enterprise_type": form.crop_type,
            "crop_type": form.crop_type,
            "business_vintage_years": form.business_vintage_years if not is_agri else "",
            "premises_status": form.premises_status if not is_agri else "",
            "customer_footfall": "Moderate (20-50/day)" if not is_agri else "",
            "land_acres": form.land_acres if is_agri else "",
            "irrigation_type": form.irrigation_type if is_agri else "",
            "monthly_income_inr": f"{income:.2f}",
            "monthly_expense_inr": f"{expense:.2f}",
            "cash_balance_inr": f"{cash:.2f}",
            "missed_utility_bills": missed,
            "overdue_installments": overdue,
            "drought_severity": f"{drought:.2f}",
            "synthetic_credit_score": score,
            "risk_pd_pct": risk_pd_pct,
            "risk_band": risk_band,
            "recommended_action": rec_step,
            "policy_decision": "MANUAL_REVIEW_REQUIRED"
        }

        # Append to CSV
        fieldnames = list(new_row.keys())
        file_exists = csv_file.exists()
        csv_file.parent.mkdir(parents=True, exist_ok=True)
        with csv_file.open("a", encoding="utf-8", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            if not file_exists:
                writer.writeheader()
            writer.writerow(new_row)

        return {"status": "SUCCESS", "application": new_row, "message": f"Loan application {app_id} created and saved to CSV!"}

    @app.get("/v1/applications/export-csv")
    async def export_applications_csv():
        csv_file = Path("data/loan_applications_faculty_demo.csv")
        if not csv_file.exists():
            raise HTTPException(status_code=404, detail="Faculty demo CSV file has not been created yet.")
        return FileResponse(csv_file, media_type="text/csv", filename="loan_applications_faculty_demo.csv")


    frontend_dir = Path(__file__).resolve().parents[2] / "frontend"
    if frontend_dir.exists():
        app.mount("/app", StaticFiles(directory=frontend_dir, html=True), name="frontend")
    return app


app = create_app()
