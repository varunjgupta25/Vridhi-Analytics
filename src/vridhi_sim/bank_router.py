"""Multi-Bank Dedicated Server Router & Node Manager for Vridhi Analytics."""

from __future__ import annotations

import csv
import json
from pathlib import Path
from fastapi import APIRouter, HTTPException, Header, Depends

ROOT = Path(__file__).resolve().parents[2]

bank_router = APIRouter(prefix="/v1/bank", tags=["Multi-Bank Dedicated Servers"])

BANK_NODES = {
    "sbi": ROOT / "servers" / "sbi_node",
    "mahb": ROOT / "servers" / "mahb_node",
    "cbin": ROOT / "servers" / "cbin_node",
    "bob": ROOT / "servers" / "bob_node",
    "pnb": ROOT / "servers" / "pnb_node",
    "ubi": ROOT / "servers" / "ubi_node",
    "canara": ROOT / "servers" / "canara_node",
    "mgb": ROOT / "servers" / "mgb_node",
    "icici": ROOT / "servers" / "icici_node",
    "hdfc": ROOT / "servers" / "hdfc_node",
}


def verify_session_token(authorization: str | None = Header(default=None)):
    """Enforces that all bank node requests have a valid session API token generated from the server."""
    from .backend import _identity, SandboxSettings
    settings = SandboxSettings.from_env()
    try:
        # Require 'loan_officer' authorization to query bank nodes
        token_data = _identity(settings, authorization, "consent:write", {"loan_officer"})
        return token_data
    except Exception as e:
        raise HTTPException(
            status_code=401,
            detail="Unauthorized access: Valid dynamic Session API Key / Bearer token is required."
        )


def load_bank_node_config(bank_code: str) -> dict:
    code = bank_code.lower()
    node_dir = BANK_NODES.get(code)
    if not node_dir or not node_dir.exists():
        raise HTTPException(status_code=404, detail=f"Dedicated Bank Server Node for '{bank_code}' not found.")

    config_file = node_dir / "config.json"
    if not config_file.exists():
        raise HTTPException(status_code=404, detail=f"Config file for Bank Node '{bank_code}' missing.")

    with config_file.open("r", encoding="utf-8") as f:
        return json.load(f)


def load_bank_borrowers(bank_code: str) -> list[dict]:
    config = load_bank_node_config(bank_code)
    data_path = ROOT / config["data_file"]

    if not data_path.exists():
        return []

    borrowers = []
    with data_path.open("r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for idx, row in enumerate(reader, start=1):
            score = int(row.get("synthetic_credit_score", 650))
            borrowers.append({
                "id": row.get("application_id", f"APP-{config['bank_code']}-{idx:03d}"),
                "farmer_id": f"entrepreneur:{row.get('pincode', '413001')}:{row.get('account_number', '001')[-3:]}",
                "account_no": row.get("account_number", ""),
                "bank_name": config["bank_name"],
                "branch_name": row.get("branch_name", ""),
                "ifsc_code": row.get("ifsc_code", ""),
                "name": row.get("borrower_name", ""),
                "village": row.get("branch_name", ""),
                "crop": row.get("crop_type", ""),
                "enterprise_type": row.get("enterprise_type", row.get("crop_type", "")),
                "pincode": row.get("pincode", "413001"),
                "on_time_payment_pct_24m": row.get("on_time_payment_pct_24m", "95%"),
                "dpd_trail_12m": row.get("dpd_trail_12m", "0-0-0-0-0-0-0-0-0-0-0-0"),
                "nach_bounces_12m": int(row.get("nach_bounces_12m", 0)),
                "avg_payment_delay_days": row.get("avg_payment_delay_days", "0.0"),
                "bbps_utility_compliance_pct": row.get("bbps_utility_compliance_pct", "96%"),
                "credit_utilization_pct": row.get("credit_utilization_pct", "32%"),
                "score": score,
                "pd": row.get("risk_pd_pct", "10.0%"),
                "band": row.get("risk_band", "Low"),
                "recommended_step": row.get("recommended_action", ""),
                "node_server": config["node_id"],
                "port": config["port"]
            })
    return borrowers


@bank_router.get("/nodes")
def get_registered_bank_nodes(token_identity: dict = Depends(verify_session_token)):
    nodes_summary = []
    for code, node_dir in BANK_NODES.items():
        if node_dir.exists():
            cfg = load_bank_node_config(code)
            nodes_summary.append({
                "code": code,
                "bank_code": cfg["bank_code"],
                "bank_name": cfg["bank_name"],
                "node_id": cfg["node_id"],
                "port": cfg["port"],
                "folder": f"servers/{code}_node/",
                "officer_roles": cfg["officer_roles"],
                "branch_pin": cfg["branch_pin"]
            })
    return {"status": "SUCCESS", "nodes": nodes_summary}


@bank_router.get("/{bank_code}/borrowers")
def get_bank_node_borrowers(bank_code: str, token_identity: dict = Depends(verify_session_token)):
    config = load_bank_node_config(bank_code)
    borrowers = load_bank_borrowers(bank_code)
    return {
        "status": "SUCCESS",
        "bank_code": config["bank_code"],
        "bank_name": config["bank_name"],
        "node_id": config["node_id"],
        "port": config["port"],
        "total_borrowers": len(borrowers),
        "borrowers": borrowers
    }
