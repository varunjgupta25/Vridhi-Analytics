# Vridhi Analytics — Project Context

Last updated: 2026-07-30

## Purpose

Vridhi is a **synthetic research and decision-support prototype** for rural credit-risk analysis. It demonstrates how cash flow, local climate stress, and economic relationships could inform a lender's manual review process.

It is **not** a production lender, a licensed NBFC/Account Aggregator, a live UPI integration, or a system authorised to automatically approve or decline a loan.

## Architecture at a glance

```text
Synthetic micro-economy simulator
  -> temporal graph dataset + synthetic repayment labels
  -> calibrated XGBoost risk model + GraphSAGE research candidate
  -> FastAPI AA-compatible sandbox + encrypted event stream
  -> lender dashboard / borrower assistant
  -> monitoring, model governance, MLflow lineage, Docker and CI
```

## Completed work

### Phase 1 — Synthetic Micro-Economy Engine

- Agent-based monthly simulator for farmers, kiranas, wholesalers, utilities, and a synthetic lender node.
- Seasonal crop income, cash balances, UPI-observed payments, utility payments, and loan repayments.
- Continuous drought input contract (`year`, `month`, `pincode`, `drought_severity`) that affects crop proceeds first, then borrower cash flow and synthetic repayment stress.
- Exports a temporal graph dataset:
  - `data/generated/reference/nodes.csv`
  - `data/generated/reference/edges.csv`
  - `data/generated/reference/node_month.csv`
  - `data/generated/reference/borrower_month_labels.csv`
  - `data/generated/reference/scenario_summary.json`

Important: the climate CSV is an adapter contract for a future approved data source. No live AI Kosha data has been ingested.

### Phase 2 — Multi-Layer Risk Engine

- Point-in-time feature builder: features at month `t` predict the synthetic 30-DPD target at `t + 1`.
- Calibrated XGBoost probability-of-default baseline.
- Native XGBoost TreeSHAP feature contributions for lender-facing explanations.
- Past-only buyer-network stress feature, capped at ±3 percentage points and disabled by default.
- Temporal GraphSAGE candidate model for research comparison.

Reference results are synthetic only:

- XGBoost: ROC-AUC `0.9894`, Brier `0.0751`.
- GraphSAGE: ROC-AUC `0.5269`, Brier `0.2761`.

The GraphSAGE candidate failed the retention gate and is **not used for scoring**.

### Phase 3 — FastAPI and AA-Compatible Sandbox

- FastAPI service with `/health`, consent, scoring, UPI-event, and stream-inspection endpoints.
- OAuth2-style client-credentials sandbox token endpoint.
- Purpose-limited, expiring, revocable consent records stored in SQLite.
- Fernet-encrypted request payloads and idempotency keys.
- Redis Streams adapter for deployment plus an in-memory adapter for tests.
- All score responses are marked `manual_review_required`.

This is a technical sandbox only. It does not implement live RBI AA, FIU, UPI, KYC, or regulatory certification.

### Phase 4 — User Interfaces

- Lender desk at `/app/`: synthetic review queue, regional-health cards, score explanation waterfall, and manual-review guardrails.
- Borrower assistant: English, Hindi, and Marathi explanation text, browser voice capture, and text-to-speech demo.
- Bhashini is an integration boundary only; no live Bhashini credentials are included.
- The current UI is a no-build Tailwind browser application because Node.js was not available on the workstation. It is served by FastAPI and can later be migrated to a bundled React application.

### Phase 5 — MLOps and Production Controls

- Model cards, training metadata, and governance artefacts.
- Feature drift monitoring using PSI and missingness changes.
- Delayed-label performance monitoring using Brier score, ROC-AUC, and average precision.
- Promotion requests are recorded as `PENDING_HUMAN_MODEL_RISK_APPROVAL`; no automatic promotion or retraining exists.
- Optional MLflow tracking integration.
- Docker Compose definitions for API, Redis, and MLflow; GitHub Actions CI workflow.

### Phase 6 — Data Admission and Real-Data Readiness

- `contracts/data_admission_contract.json` records data classification, required source fields, and the controls that must exist before real data can enter research.
- `vridhi_sim.data_readiness_cli` validates schema, synthetic provenance, duplicates, numeric/timestamp bounds, and point-in-time leakage.
- Reference reports are written to `artifacts/validation/reference/`.
- A clean synthetic dataset is always reported as `SYNTHETIC_RESEARCH_ONLY`; the gate never permits real borrower scoring or automated underwriting.

### Phase 7 — Manual-Review Policy and Fairness Diagnostics

- `contracts/manual_review_policy.json` versions the manual-review guardrails.
- `vridhi_sim.policy_cli` creates policy records, explanation drafts, minimal audit records, and PIN-code cohort diagnostics from synthetic scores.
- No policy output can approve, decline, or price a loan. Every result is `MANUAL_REVIEW_REQUIRED` and its final lending decision is `NOT_MADE`.
- Drought, geography, UPI coverage, language, and buyer-network coverage are explicitly prohibited as sole adverse reasons.
- The lender dashboard exposes only an aggregate **Policy & Fairness** panel through `/v1/policy/reference-summary`; it does not expose raw audit records or financial payloads.

### Phase 8 — Integration-Security Sandbox

- Role-limited sandbox tokens support `loan_officer`, `reviewer`, and `admin` actions. The common sandbox secret is a local-demo convenience and must never be used outside development.
- Synthetic partner events require an HMAC signature and are accepted only by an admin role; no live partner, FIU, AA, UPI, or lender connection exists.
- AA/FIU data schema contracts (`contracts/aa_fiu_contract.json`), KYC masking/PII hashing, AML sanction check stubs, and Bhashini NMT localization boundaries are implemented.
- An automated penetration test harness in `vridhi_sim.security_cli` verifies HMAC signature integrity, rate limiting, tamper-evident audit ledger verification, and RBAC scope isolation.
- An emergency kill-switch controller (`POST /v1/admin/kill-switch`) freezes scoring immediately into 503 manual-review mode.

### Phase 9 — Shadow-Mode Pilot Engine

- `vridhi_sim.shadow_engine` and `vridhi_sim.shadow_cli` run non-intrusive parallel evaluations alongside lender decisions.
- Tracks decision disagreement rates, ROC-AUC / Brier score divergence against 30-DPD labels, operational latency deltas, and qualitative loan officer feedback.
- Generates `artifacts/shadow/reference/shadow_pilot_report.json`.

### Phase 10 — Controlled Production Rollout & Governance Engine

- `vridhi_sim.rollout` and `vridhi_sim.rollout_cli` manage stage-gated rollout progression (`STAGE_0` through `STAGE_3`) and enforce pincode/volume boundaries.
- Automated rollback triggers freeze the system if Brier score > 0.15, PSI drift > 0.25, or error rate > 1.0%.
- Generates formal `artifacts/governance/reference/production_rollout_certificate.json`. Automated decision-making is strictly disabled; every loan decision requires a human underwriter.

## Main entry points

From the project root:

```powershell
$env:PYTHONPATH = "src"
```

Generate the synthetic reference scenario:

```powershell
python -m vridhi_sim.cli --output data/generated/reference --climate-shocks data/climate_shocks.example.csv --seed 42
```

Train the reference risk model:

```powershell
python -m vridhi_sim.risk_cli --dataset data/generated/reference --output artifacts/risk/reference
```

Run the API and UI:

```powershell
python -m vridhi_sim.api_cli
```

Validate the synthetic data admission gate:

```powershell
python -m vridhi_sim.data_readiness_cli --dataset data/generated/reference --output artifacts/validation/reference
```

Generate Phase 7 policy and monitoring artifacts:

```powershell
python -m vridhi_sim.policy_cli --scores artifacts/risk/reference/research_scores.csv --dataset data/generated/reference --output artifacts/policy/reference
```

Generate a Phase 8 security readiness report:

```powershell
python -m vridhi_sim.security_cli --audit-ledger runtime/security_audit.jsonl --output artifacts/security/reference/security_readiness.json
```

Open:

- User interface: `http://127.0.0.1:8000/app/`
- API documentation: `http://127.0.0.1:8000/docs`

Run tests:

```powershell
python -m pytest
```

## MLOps artefacts

- `artifacts/risk/reference/model_card.json`
- `artifacts/risk/reference/risk_engine_metadata.json`
- `artifacts/monitoring/reference/drift_report.json`
- `artifacts/monitoring/reference/delayed_label_performance.json`
- `artifacts/governance/reference_promotion_request.json`

The latest reference monitoring report is `STABLE`; this only means the reference dataset matches itself. It does not validate behaviour on real borrowers.

## Known environment issue

The installed MLflow version can record tracking runs from the current Python 3.14 environment, but its local Windows web server crashes under Python 3.14 with an `importlib.abc.Traversable` import error.

- Do not use the MLflow UI from Python 3.14.
- Use Python 3.13 or the Docker stack for the MLflow server/UI.
- The project Dockerfile and CI workflow have been set to Python 3.13 for this reason.

## Non-negotiable safety constraints

- Synthetic labels do not prove real lending performance.
- A low UPI footprint must not be interpreted as low creditworthiness.
- Climate, geography, language, and relationship signals must not become unchecked automated denial reasons.
- Real deployment requires a regulated lender/FIU partner, consented data, legal review, model validation, privacy controls, and human decision governance.
