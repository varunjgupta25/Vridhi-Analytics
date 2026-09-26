"""Phase 10 CLI for generating Controlled Production Rollout Governance Certificates."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from .rollout import ProductionRolloutManager


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate Vridhi Phase 10 Production Rollout Governance Certificate.")
    parser.add_argument("--data-readiness", type=Path, default=Path("artifacts/validation/reference/data_readiness_report.json"))
    parser.add_argument("--security-readiness", type=Path, default=Path("artifacts/security/sandbox_security_readiness.json"))
    parser.add_argument("--shadow-report", type=Path, default=Path("artifacts/shadow/reference/shadow_pilot_report.json"))
    parser.add_argument("--output", type=Path, default=Path("artifacts/governance/reference"))
    args = parser.parse_args()

    data_report = json.loads(args.data_readiness.read_text(encoding="utf-8")) if args.data_readiness.exists() else None
    sec_report = json.loads(args.security_readiness.read_text(encoding="utf-8")) if args.security_readiness.exists() else None
    shadow_report = json.loads(args.shadow_report.read_text(encoding="utf-8")) if args.shadow_report.exists() else None

    manager = ProductionRolloutManager()
    cert = manager.generate_governance_certificate(data_report, sec_report, shadow_report)

    args.output.mkdir(parents=True, exist_ok=True)
    cert_file = args.output / "production_rollout_certificate.json"
    manager.save_certificate(cert, cert_file)

    print(f"Phase 10 Governance Certificate generated.")
    print(f"Certificate File: {cert_file.resolve()}")
    print(f"Certificate ID: {cert['certificate_id']}")
    print(f"Approval Status: {cert['approval_status']}")


if __name__ == "__main__":
    main()
