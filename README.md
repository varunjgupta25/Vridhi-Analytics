# Vridhi — Phase 1 Synthetic Micro-Economy Engine

This package generates a reproducible, **causal** synthetic rural-economy dataset. It is intentionally not a random transaction generator and not a validated production credit model.

The simulator creates four core agent types:

- Farmers: sell seasonal crop output to wholesalers, buy necessities from kiranas, pay utilities, and service a synthetic micro-loan.
- Kiranas: receive household spend from farmers, replenish from wholesalers, and pay utilities.
- Wholesalers: buy crop output from farmers and receive retailer replenishment payments.
- Utility companies: receive electricity and irrigation payments.

It also creates a synthetic lender node solely to model scheduled repayments and repayment stress. This is an explicit modelling convenience, not a fifth economic population.

## What makes it causal

At each monthly step, crop yield and sale proceeds are calculated from a farmer's crop type, irrigation resilience, seasonal base income, market-price variation, and the local drought severity. The shock passes through income, cash balance, missed utility/loan payments, repayment ability, and finally the exported monthly borrower label.

`climate_shocks.csv` is an adapter contract for later AI Kosha or other approved sources. The repository includes only illustrative synthetic shock data; it does not claim to contain or call live AI Kosha data.

## Outputs

Running the command below writes an interoperable temporal graph dataset:

```powershell
python -m vridhi_sim.cli --output data/generated/reference --seed 42
```

- `nodes.csv` — graph nodes and static attributes
- `edges.csv` — timestamped directed UPI-like payment edges
- `node_month.csv` — point-in-time cash-flow and stress features
- `borrower_month_labels.csv` — explicitly synthetic repayment labels
- `scenario_summary.json` — parameters, shock counts, and aggregates

## Climate shock input contract

Provide a CSV with this schema:

```text
year,month,pincode,drought_severity
2025,7,413001,0.72
```

`drought_severity` is in `[0, 1]`; it is deliberately a continuous intensity, not a binary “drought year.” A production data adapter must validate provenance, spatial resolution, crop relevance, licence, and freshness before supplying this input.

## Important limitations

- UPI is only one payment channel. The simulator records an unobserved cash share so that absent digital transactions are not treated as absent economic activity.
- PIN codes are used only as scenario partitions. They are not treated as agronomic truth.
- Simulated repayment labels are useful for pipeline tests, stress scenarios, and demonstrations—not for proving real-world model accuracy or lending policy.
- Calibration must compare distributions and shock responses with independently permitted aggregate data before any research claim is made.

## Tests

```powershell
python -m pytest
```

## Phase 2 — Synthetic research risk engine

Phase 2 trains a calibrated XGBoost probability-of-default research model on
**point-in-time** farmer-month features. Features at month `t` are paired only
with the synthetic 30-DPD label from month `t + 1`; the current or future label
is never an input feature.

```powershell
$env:PYTHONPATH = "src"
python -m vridhi_sim.risk_cli --dataset data/generated/reference --output artifacts/risk/reference
```

The command produces a serialized model, evaluation metadata, and a score file.
Every result is marked `manual_review_required`; it is not an automatic loan
approval or rejection system.

The relational layer uses past observed crop-buyer links to calculate a bounded
buyer-network stress signal. It is disabled by default, limited to a maximum
3-percentage-point probability adjustment when explicitly enabled, and does not
expose a buyer identity in a borrower explanation. A true GNN is intentionally
kept as a validation-gated research candidate until a real, consented,
temporally validated outcome dataset shows incremental value over this baseline.

To run the candidate experiment separately:

```powershell
$env:PYTHONPATH = "src"
python -m vridhi_sim.risk_cli --dataset data/generated/reference --output artifacts/risk/reference --train-gnn-candidate
```

The candidate is a temporal GraphSAGE implementation using only edges before the
score month. Its metrics are written separately and it is never ensembled into
the score merely because it exists. The reference scenario currently rejects it
because it underperforms the XGBoost baseline.

Explanations are native XGBoost TreeSHAP feature contributions for the tabular
model. Calibration and the optional relational overlay are reported separately;
neither is presented as causal proof.

## Phase 3 — Account Aggregator-compatible security sandbox

Phase 3 adds a local FastAPI sandbox around the synthetic model. It is **not** a
licensed Account Aggregator, an FIU, an RBI-approved integration, or a live UPI
connection. It demonstrates the technical controls a real integration would
need: scoped short-lived access tokens, purpose-limited consent records,
encrypted envelopes, idempotency keys, audit-friendly stream metadata, and
consent revocation.

```powershell
$env:PYTHONPATH = "src"
python -m vridhi_sim.api_cli
```

`POST /v1/oauth/token` uses the OAuth2 client-credentials form shape. The local
defaults are `sandbox-client` / `sandbox-secret` and must be replaced outside
development. Both tokens and financial payloads use Fernet encryption. Set
`VRIDHI_SANDBOX_TOKEN_KEY` and `VRIDHI_SANDBOX_PAYLOAD_KEY` to independent
Fernet keys for any shared environment.

The API accepts only encrypted synthetic data after a purpose-limited consent
has been created. It publishes encrypted-transaction metadata and score events
through Redis Streams when `REDIS_URL` is set; otherwise it uses an in-memory
test adapter. Run the local stack with:

```powershell
docker compose up --build
```

## Phase 4 — Lender and borrower interfaces

Open `http://127.0.0.1:8000/app/` while the API is running. The lender desk
shows a manual-review queue, a privacy-preserving regional-health view, and a
clear score-explanation waterfall. The borrower assistant provides English,
Hindi, and Marathi explanation copy plus a browser voice demo.

The current workstation has no Node.js runtime, so this interface is served as
a no-build Tailwind browser application. The visual and interaction design is
ready for a React build migration once Node is installed. Bhashini is kept as a
documented integration boundary; no live Bhashini credentials are embedded.

## Phase 5 — MLOps and production controls

Every risk-training run writes a model card, metrics, and governance metadata.
To track a reviewed synthetic run in MLflow, provide a tracking URI:

```powershell
$env:PYTHONPATH = "src"
python -m vridhi_sim.risk_cli --dataset data/generated/reference --output artifacts/risk/reference --mlflow-tracking-uri sqlite:///artifacts/mlflow/mlflow.db
```

Generate drift and delayed-label performance reports with:

```powershell
python -m vridhi_sim.mlops_cli monitor --reference-dataset data/generated/reference --current-dataset data/generated/reference --scores artifacts/risk/reference/research_scores.csv
```

Drift creates `REVIEW_REQUIRED` alerts; it never retrains or promotes a model.
Promotion creates a human model-risk approval request only. The Docker Compose
stack includes MLflow at `http://127.0.0.1:5000`.

The local MLflow web server must currently be run with Python 3.13 (the installed
MLflow server crashes under Python 3.14 on Windows). The tracking run itself can
still be recorded from the existing environment. Use the Docker stack or a
Python 3.13 virtual environment for the MLflow UI.

## Phase 6 — Data admission and real-data readiness

Phase 6 is deliberately a gate before any future partner or customer dataset is
considered. It validates the dataset contract, synthetic provenance, timestamps,
numeric bounds, duplicate records, and the point-in-time separation between
features at month `t` and labels at month `t + 1`.

```powershell
$env:PYTHONPATH = "src"
python -m vridhi_sim.data_readiness_cli --dataset data/generated/reference --output artifacts/validation/reference
```

It produces `quality_report.json` and `data_readiness_report.json`. A passing
report means only that the files are clean enough for **synthetic research**.
It does not authorize real-data ingestion, real borrower scoring, or automated
underwriting. The requirements that must be met before real data is admitted are
recorded in `contracts/data_admission_contract.json` and in the readiness report.

## Phase 7 — Manual-review policy, fairness diagnostics, and audit records

Phase 7 places a versioned human-review policy around every model score. It can
assign a review priority, but it never approves, declines, or prices a loan.
Explanation drafts separate direct financial factors from contextual signals
such as drought or network coverage; contextual signals are prohibited as sole
adverse reasons.

```powershell
$env:PYTHONPATH = "src"
python -m vridhi_sim.policy_cli --scores artifacts/risk/reference/research_scores.csv --dataset data/generated/reference --output artifacts/policy/reference
```

The command writes manual-review records, minimised audit events, and a PIN-code
cohort diagnostic. This is not a legal or real-world fairness claim: the data
and outcomes are synthetic, and PIN codes are scenario partitions.

When the FastAPI sandbox is running, the lender desk at
`http://127.0.0.1:8000/app/` also displays a **Policy & Fairness** panel. It
loads only aggregate synthetic diagnostics: the number of manual-review records,
the policy version, cohort coverage, and the review-required status. It never
exposes audit identifiers or raw borrower financial data in the dashboard.

## Phase 8 — Integration-security sandbox

Phase 8 hardens the local sandbox without connecting it to a lender, FIU, UPI,
or Account Aggregator. It provides short-lived role-limited tokens for sandbox
loan officers, reviewers, and admins; rate limiting; HMAC-signed **synthetic**
partner webhooks; a hash-chained audit ledger; and an admin-triggered retention
job that can purge expired synthetic metadata.

```powershell
$env:PYTHONPATH = "src"
python -m vridhi_sim.security_cli --audit-ledger runtime/security_audit.jsonl --output artifacts/security/reference/security_readiness.json --run-pentest
```

The lender desk's **Integration security** panel displays aggregate status only.
It never displays secret values, raw audit events, or financial payloads. The
controls are described in `contracts/security_sandbox_controls.json` and `contracts/aa_fiu_contract.json`;
they are not a replacement for production secret management, a regulated partner review,
or external security testing.

## Phase 9 — Shadow-mode pilot evaluation

Phase 9 evaluates Vridhi model recommendations side-by-side with existing lender
decisions without influencing actual lending. It tracks decision disagreement rates,
ROC-AUC / Brier score divergence against 30-DPD labels, operational latency deltas,
and qualitative loan officer feedback.

```powershell
$env:PYTHONPATH = "src"
python -m vridhi_sim.shadow_cli --scores artifacts/risk/reference/research_scores.csv --dataset data/generated/reference --output artifacts/shadow/reference
```

It writes `artifacts/shadow/reference/shadow_pilot_report.json`.

## Phase 10 — Controlled production rollout & governance

Phase 10 enforces regulated partner bounds (`contracts/regulated_partner_contract.json`),
volume/pincode stage limits, automated metric-driven rollback triggers (Brier score > 0.15,
PSI drift > 0.25, or error rate > 1.0%), emergency kill-switch controls (`POST /v1/admin/kill-switch`),
and generates a formal Governance Certificate.

```powershell
$env:PYTHONPATH = "src"
python -m vridhi_sim.rollout_cli --data-readiness artifacts/validation/reference/data_readiness_report.json --security-readiness artifacts/security/reference/security_readiness.json --shadow-report artifacts/shadow/reference/shadow_pilot_report.json --output artifacts/governance/reference
```

It writes `artifacts/governance/reference/production_rollout_certificate.json`. All automated decision-making remains disabled; every loan decision requires a human underwriter.
