"""Generate a non-sensitive Phase 8 sandbox-security readiness report."""

from __future__ import annotations

import argparse
from datetime import UTC, datetime
from pathlib import Path

from .mlops import write_json
from .security import DEFAULT_CLIENT_ROLES, ROLE_SCOPES, TamperEvidentAuditLedger, run_security_pentest


def main() -> None:
    parser = argparse.ArgumentParser(description="Inspect Vridhi's synthetic Phase 8 security controls.")
    parser.add_argument("--audit-ledger", type=Path, default=Path("runtime/security_audit.jsonl"))
    parser.add_argument("--output", type=Path, default=Path("artifacts/security/sandbox_security_readiness.json"))
    parser.add_argument("--run-pentest", action="store_true", help="Run automated security penetration test harness")
    args = parser.parse_args()

    pentest_results = None
    if args.run_pentest:
        pentest_results = run_security_pentest(args.audit_ledger)

    report = {
        "generated_at": datetime.now(UTC).isoformat(),
        "scope": "synthetic integration sandbox only",
        "live_partner_connections": False,
        "real_personal_data_supported": False,
        "client_roles": DEFAULT_CLIENT_ROLES,
        "allowed_scopes_by_role": {role: sorted(scopes) for role, scopes in ROLE_SCOPES.items()},
        "signed_partner_webhooks": "SIMULATED_HMAC_ONLY",
        "audit_ledger": TamperEvidentAuditLedger(args.audit_ledger).verify(),
        "retention": "ADMIN_TRIGGERED_EXPIRED_SYNTHETIC_METADATA_ONLY",
        "pentest_harness": pentest_results or {"pentest_status": "SKIPPED"},
        "production_blockers": [
            "No regulated partner, FIU, or lender integration has been approved.",
            "No production secret manager, key-management system, or external penetration test is configured.",
            "No real customer data may be sent to this sandbox.",
        ],
    }
    write_json(args.output, report)
    print(f"Sandbox security report written to {args.output.resolve()}; live integrations remain disabled.")


if __name__ == "__main__":
    main()
