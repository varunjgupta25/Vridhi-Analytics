"""Phase 6 data-admission and synthetic-to-real validation controls.

This validates only Vridhi's synthetic research files. It deliberately does not
make real financial information admissible merely because it resembles a CSV.
"""

from __future__ import annotations

import csv
import json
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


REQUIRED_COLUMNS: dict[str, tuple[str, ...]] = {
    "nodes.csv": ("entity_id", "entity_type", "pincode", "synthetic"),
    "edges.csv": ("event_id", "timestamp", "source_id", "target_id", "amount_inr", "transaction_type", "channel", "pincode", "drought_severity", "synthetic"),
    "node_month.csv": ("month", "entity_id", "entity_type", "pincode", "cash_balance", "income_inr", "expense_inr", "net_cash_flow_inr", "income_volatility_3m", "missed_utility_payments", "overdue_installments", "drought_severity", "repayment_ability_proxy", "synthetic"),
    "borrower_month_labels.csv": ("month", "farmer_id", "pincode", "synthetic_30dpd", "synthetic_60dpd", "repayment_ability_proxy", "drought_severity", "label_origin"),
}
FORBIDDEN_POINT_IN_TIME_FEATURES = ("synthetic_30dpd", "synthetic_60dpd", "target_30dpd")


def _now() -> str:
    return datetime.now(UTC).isoformat()


def _read_csv(path: Path) -> tuple[list[str], list[dict[str, str]]]:
    with path.open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        return list(reader.fieldnames or []), list(reader)


def _truthy(value: str | None) -> bool:
    return str(value).strip().lower() in {"true", "1", "yes"}


def _month(value: str) -> bool:
    try:
        datetime.strptime(value, "%Y-%m-%d")
        return value.endswith("-01")
    except ValueError:
        return False


def _timestamp(value: str) -> bool:
    try:
        datetime.strptime(value, "%Y-%m-%dT%H:%M:%SZ")
        return True
    except ValueError:
        return False


def _next_month(value: str) -> str:
    parsed = datetime.strptime(value, "%Y-%m-%d")
    year, month = parsed.year, parsed.month
    return f"{year + (month == 12):04d}-{1 if month == 12 else month + 1:02d}-01"


def _number(value: str, minimum: float | None = None, maximum: float | None = None) -> bool:
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return False
    return (minimum is None or parsed >= minimum) and (maximum is None or parsed <= maximum)


def _integer_in(value: str, allowed: set[int]) -> bool:
    try:
        return int(value) in allowed and str(int(value)) == str(value).strip()
    except (TypeError, ValueError):
        return False


def _issue(issues: list[dict[str, str]], code: str, detail: str) -> None:
    issues.append({"code": code, "severity": "error", "detail": detail})


def _duplicates(rows: list[dict[str, str]], keys: tuple[str, ...]) -> int:
    counts = Counter(tuple(row.get(key, "") for key in keys) for row in rows)
    return sum(count - 1 for count in counts.values() if count > 1)


def _load_tables(dataset_dir: Path, issues: list[dict[str, str]]) -> dict[str, tuple[list[str], list[dict[str, str]]]]:
    tables: dict[str, tuple[list[str], list[dict[str, str]]]] = {}
    for filename, required in REQUIRED_COLUMNS.items():
        path = dataset_dir / filename
        if not path.exists():
            _issue(issues, "missing_file", f"Required dataset is absent: {filename}.")
            continue
        fields, rows = _read_csv(path)
        tables[filename] = (fields, rows)
        missing = sorted(set(required) - set(fields))
        if missing:
            _issue(issues, "missing_columns", f"{filename} is missing: {', '.join(missing)}.")
        if not rows:
            _issue(issues, "empty_dataset", f"{filename} has no records.")
        if "synthetic" in fields and any(not _truthy(row.get("synthetic")) for row in rows):
            _issue(issues, "non_synthetic_record", f"{filename} contains a record not marked synthetic.")
    return tables


def _check_records(tables: dict[str, tuple[list[str], list[dict[str, str]]]], issues: list[dict[str, str]]) -> None:
    _, nodes = tables.get("nodes.csv", ([], []))
    if count := _duplicates(nodes, ("entity_id",)):
        _issue(issues, "duplicate_node_id", f"nodes.csv contains {count} duplicate entity_id values.")

    _, edges = tables.get("edges.csv", ([], []))
    if count := _duplicates(edges, ("event_id",)):
        _issue(issues, "duplicate_event_id", f"edges.csv contains {count} duplicate event_id values.")
    invalid_edges = sum(not _timestamp(row.get("timestamp", "")) or row.get("source_id") == row.get("target_id") or not _number(row.get("amount_inr", ""), 0.01) or not _number(row.get("drought_severity", ""), 0.0, 1.0) for row in edges)
    if invalid_edges:
        _issue(issues, "invalid_transaction_record", f"edges.csv contains {invalid_edges} invalid records.")

    fields, snapshots = tables.get("node_month.csv", ([], []))
    leaked = [field for field in fields if field in FORBIDDEN_POINT_IN_TIME_FEATURES]
    if leaked:
        _issue(issues, "outcome_leakage_column", f"node_month.csv contains prohibited outcome columns: {', '.join(leaked)}.")
    if count := _duplicates(snapshots, ("month", "entity_id")):
        _issue(issues, "duplicate_snapshot", f"node_month.csv contains {count} duplicate snapshots.")
    invalid_snapshots = sum(not _month(row.get("month", "")) or not _number(row.get("cash_balance", ""), 0.0) or not _number(row.get("income_inr", ""), 0.0) or not _number(row.get("expense_inr", ""), 0.0) or not _number(row.get("income_volatility_3m", ""), 0.0) or not _number(row.get("drought_severity", ""), 0.0, 1.0) or not _number(row.get("repayment_ability_proxy", ""), 0.0) or not _integer_in(row.get("missed_utility_payments", ""), set(range(1000))) or not _integer_in(row.get("overdue_installments", ""), set(range(1000))) for row in snapshots)
    if invalid_snapshots:
        _issue(issues, "invalid_snapshot_record", f"node_month.csv contains {invalid_snapshots} invalid point-in-time records.")

    _, labels = tables.get("borrower_month_labels.csv", ([], []))
    if count := _duplicates(labels, ("month", "farmer_id")):
        _issue(issues, "duplicate_label", f"borrower_month_labels.csv contains {count} duplicate labels.")
    invalid_labels = sum(not _month(row.get("month", "")) or not _integer_in(row.get("synthetic_30dpd", ""), {0, 1}) or not _integer_in(row.get("synthetic_60dpd", ""), {0, 1}) or not _number(row.get("drought_severity", ""), 0.0, 1.0) or row.get("label_origin") != "simulator_rule_not_real_credit_outcome" for row in labels)
    if invalid_labels:
        _issue(issues, "invalid_label_record", f"borrower_month_labels.csv contains {invalid_labels} invalid or non-synthetic outcome records.")


def _temporal_alignment(tables: dict[str, tuple[list[str], list[dict[str, str]]]], issues: list[dict[str, str]]) -> dict[str, Any]:
    _, snapshots = tables.get("node_month.csv", ([], []))
    _, labels = tables.get("borrower_month_labels.csv", ([], []))
    snapshots_at_t = {(row.get("month"), row.get("entity_id")) for row in snapshots}
    per_farmer: dict[str, list[str]] = {}
    for label in labels:
        per_farmer.setdefault(label.get("farmer_id", ""), []).append(label.get("month", ""))
    pairs = missing = non_consecutive = 0
    for farmer, months in per_farmer.items():
        ordered = sorted(months)
        for current, following in zip(ordered, ordered[1:]):
            pairs += 1
            if (current, farmer) not in snapshots_at_t:
                missing += 1
            if _month(current) and _month(following) and following != _next_month(current):
                non_consecutive += 1
    if missing:
        _issue(issues, "missing_feature_snapshot_for_outcome", f"{missing} t-to-t+1 label pairs have no feature snapshot at t.")
    if non_consecutive:
        _issue(issues, "non_consecutive_outcome_month", f"{non_consecutive} label pairs are not consecutive t-to-t+1 months.")
    return {"feature_time": "month_t", "outcome_time": "month_t_plus_1", "eligible_farmer_month_pairs": pairs, "missing_feature_snapshots": missing, "non_consecutive_label_pairs": non_consecutive, "status": "PASS" if not missing and not non_consecutive else "FAIL"}


def validate_synthetic_dataset(dataset_dir: Path) -> dict[str, Any]:
    """Validate the only data class currently supported: synthetic Vridhi data."""
    dataset_dir = Path(dataset_dir)
    issues: list[dict[str, str]] = []
    tables = _load_tables(dataset_dir, issues)
    synthetic_only = False
    scenario = dataset_dir / "scenario_summary.json"
    if not scenario.exists():
        _issue(issues, "missing_scenario_summary", "scenario_summary.json is required to establish provenance.")
    else:
        try:
            synthetic_only = json.loads(scenario.read_text(encoding="utf-8")).get("synthetic_only") is True
            if not synthetic_only:
                _issue(issues, "unverified_provenance", "scenario_summary.json does not certify synthetic_only=true.")
        except json.JSONDecodeError:
            _issue(issues, "invalid_scenario_summary", "scenario_summary.json is not valid JSON.")
    _check_records(tables, issues)
    temporal = _temporal_alignment(tables, issues)
    return {"schema_version": "1.0", "generated_at": _now(), "dataset_dir": str(dataset_dir), "declared_data_classification": "synthetic" if synthetic_only else "unverified", "admission_scope": "synthetic_research_only", "overall_status": "PASS" if not issues else "FAIL", "tables": {name: {"rows": len(rows), "columns": fields} for name, (fields, rows) in tables.items()}, "temporal_alignment": temporal, "issues": issues}


def synthetic_to_real_readiness(validation: dict[str, Any]) -> dict[str, Any]:
    """State the non-negotiable gap between a clean synthetic dataset and deployment."""
    quality_passed = validation.get("overall_status") == "PASS"
    return {"schema_version": "1.0", "generated_at": _now(), "current_dataset_classification": validation.get("declared_data_classification"), "data_quality_status": validation.get("overall_status"), "decision": "SYNTHETIC_RESEARCH_ONLY" if quality_passed else "DATA_QUALITY_FAILURE", "real_borrower_scoring_allowed": False, "automatic_underwriting_allowed": False, "reason": "The dataset passed synthetic-data checks but has simulation labels and no consented real-world outcomes." if quality_passed else "Fix the reported validation errors before using this dataset even for synthetic research.", "required_before_any_real_data_admission": ["A partner-approved, field-level contract: source owner, permitted purpose, retention, deletion, and access roles.", "A purpose-limited consent or other approved legal basis, plus revocation and audit handling.", "Source provenance, completeness, reconciliation, and transaction-coverage testing.", "Independently observed delayed outcomes and point-in-time validation on a held-out time period.", "Privacy, security, fairness, human-oversight, and model-risk approval before a controlled pilot."], "next_gate": "Phase 7 policy, fairness, and adverse-action controls; no partner data should be ingested yet."}


def write_json(path: Path, payload: dict[str, Any]) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return path
