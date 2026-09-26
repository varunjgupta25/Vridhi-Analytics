"""Generate Phase 7 policy, fairness, explanation, and audit artifacts."""

from __future__ import annotations

import argparse
from pathlib import Path

from .policy import audit_record, evaluate_manual_review, fairness_diagnostic, read_scores, write_audit_jsonl, write_json
from .risk_engine import build_learning_dataset


def main() -> None:
    parser = argparse.ArgumentParser(description="Run Vridhi's synthetic manual-review policy controls.")
    parser.add_argument("--scores", type=Path, required=True)
    parser.add_argument("--dataset", type=Path, required=True)
    parser.add_argument("--output", type=Path, default=Path("artifacts/policy"))
    parser.add_argument("--actor", default="synthetic-policy-runner")
    args = parser.parse_args()
    scores = read_scores(args.scores)
    decisions = [{"farmer_id": score["farmer_id"], "month": score["month"], "policy": evaluate_manual_review(score)} for score in scores]
    audits = [audit_record(score, decision["policy"], args.actor) for score, decision in zip(scores, decisions)]
    fairness = fairness_diagnostic(decisions, build_learning_dataset(args.dataset))
    write_json(args.output / "manual_review_decisions.json", decisions)
    write_json(args.output / "fairness_diagnostic.json", fairness)
    write_audit_jsonl(args.output / "policy_audit.jsonl", audits)
    print(f"Created {len(decisions)} manual-review records; fairness status: {fairness['overall_status']}.")
    print(f"No approvals or declines were generated. Artifacts written to {args.output.resolve()}.")


if __name__ == "__main__":
    main()
