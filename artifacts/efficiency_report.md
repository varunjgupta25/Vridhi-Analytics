# Vridhi Analytics — Corrected ML Efficiency Report

> **Audit revision 2 (commit post-`6b4004a`)**: This report was rewritten after two rounds of
> codebase audit:
>
> **Round 1** found fabricated efficiency constants (`14.2 ms`, `1200 ms`, `~2.5 s`, `<80 MB`)
> and replaced them with instrumented code.
>
> **Round 2** (this revision) found that the Round 1 latency measurement was itself
> meaningless — it timed `np.where` on an already-computed PD array, not the actual
> scoring path — and that `tracemalloc` was mislabelled as process RSS when it only
> tracks the Python heap.  Both issues are now fixed.  The report also corrected an
> arithmetic inconsistency in the previous draft (agreement rate 95.07 % with
> disagreement rate 0.4930 is impossible; the correct figure was 0.0493, and the
> freshly regenerated run gives 0.0472 / 95.28 %).
>
> **Accuracy metrics (ROC-AUC/Brier/AP) were not changed across either round** — they
> were already correct and are verified by the training pipeline.

---

## 1. Predictive Accuracy (verified, unchanged across both audits)

Source: `risk_engine_metadata.json` and `delayed_label_performance.json`, written by
the training pipeline using sklearn's `roc_auc_score`, `brier_score_loss`, and
`average_precision_score` on a strictly out-of-time held-out test set.

| Metric | Out-of-Time Test Set | Delayed-Label Monitor | Notes |
|:---|:---:|:---:|:---|
| **ROC-AUC** | **0.9893** | **0.9940** | Strictly time-ordered test split; no data leakage |
| **Brier Score Loss** | **0.0746** | **0.0301** | Lower = better calibrated probabilities |
| **Average Precision (PR-AUC)** | **0.9840** | **0.9708** | High-recall precision on imbalanced default labels |
| **Training rows** | 1,365 | — | First 60 % of months |
| **Calibration rows** | 525 | — | Middle 20 % of months (Platt scaling only) |
| **Test rows** | 525 | 2,415 | Final 20 % of months; no overlap with train/cal |
| **Test default rate** | 41.3 % | 18.9 % | Synthetic label distribution |

> **Note on GraphSAGE research candidate**: ROC-AUC 0.5269, Brier 0.2761.
> Failed the retention gate; permanently excluded from scoring.

---

## 2. Inference Latency (real measurement — full scoring path)

**What is timed**: the complete per-row scoring path:
1. `_matrix(rows)` — feature-matrix construction from raw row dicts
2. `XGBClassifier.predict_proba` — base model forward pass
3. `LogisticRegression.predict_proba` — Platt calibration
4. `explain()` per row — native XGBoost TreeSHAP contributions (top-3 features)
5. Risk-band classification and synthetic credit-score mapping

**What is not timed**: model load from disk, CSV I/O (one-time / data-volume costs).

**Method**: `time.perf_counter()` with 1 warm-up pass (discarded) then 5 timed
passes over all 2,415 rows.  Mean per-row wall-clock from `shadow_pilot_report.json`.

| Measurement | Value | Source |
|:---|:---:|:---|
| **`vridhi_avg_latency_ms`** | **0.8767 ms/row** | `shadow_pilot_report.json` (this run) |
| `latency_path_complete` | `true` | Full scoring path was exercised |
| `baseline_avg_latency_ms` | `null` | Not measured — no real lender inference process available |

> **Previous fabricated value** (removed): 14.2 ms hardcoded literal — never connected
> to any timing code.  **Round 1 replacement** (also wrong): timed `np.where` on a
> pre-computed array, producing 0.0 ms.  The current figure is the real cost.

---

## 3. Training Duration & Memory (real measurements, dual-labelled)

Source: `risk_engine_metadata.json → training_profile`.  Written by `risk_cli.py`
using stdlib-only profiling tools.

| Measurement | Value | API | Covers | Caveats |
|:---|:---:|:---|:---|:---|
| **`train_wall_clock_seconds`** | **0.119 s** | `time.perf_counter()` | `RiskEngine.fit()` wall-clock | Excludes dataset loading and I/O |
| **`python_heap_peak_mb`** | **0.44 MB** | `tracemalloc.get_traced_memory()` | Python object heap only | **Does NOT include XGBoost native C allocations** — almost certainly understates true memory |
| **`process_rss_mb`** | **173.73 MB** | `ctypes + psapi.GetProcessMemoryInfo` (Windows) | Full process WorkingSetSize — includes XGBoost C heap | Snapshot after `fit()` completes, not a peak |

> **Previous fabricated values** (removed): "~2.5 s training", "<80 MB RAM" — neither
> was grounded in any profiling code.  The two-figure approach (Python-heap vs.
> process RSS) is intentional: `tracemalloc` is accurate for Python-side allocations,
> while Windows WorkingSetSize captures what the OS actually assigns to the process
> (including XGBoost's native C allocations that `tracemalloc` cannot see).

> [!NOTE]
> On Linux/macOS, `process_rss_mb` is measured via
> `resource.getrusage(RUSAGE_SELF).ru_maxrss` (a true peak RSS), which is even
> more accurate.  On Windows the WorkingSetSize is a point-in-time snapshot —
> the `process_rss_note` field in the JSON explains this for each platform.

---

## 4. Shadow-Mode Pilot Concordance (vs synthetic noise baseline)

> [!WARNING]
> The shadow pilot was run **without a real lender baseline**.  The comparison
> partner is a **synthetic Gaussian noise-perturbed proxy** (`seed=42`,
> `σ = 0.15` applied to Vridhi PD).  This is an internal engineering sanity
> check, not a comparison against any real bank, NBFC, or credit bureau process.

Source: freshly regenerated `shadow_pilot_report.json`.

| Metric | Value | Source field |
|:---|:---:|:---|
| **Total shadow evaluations** | 2,415 | `total_evaluations` |
| **Decision agreements** | 2,408 (95.28 %) | `decision_matrix.agreements` |
| **Decision disagreements** | 7 (0.29 %) | `decision_matrix.disagreements` |
| **Disagreement rate (PD gap > 0.25)** | **0.0472** (4.72 %) | `disagreement_rate` |
| **`vridhi_avg_latency_ms`** | **0.8767 ms/row** | `latency_metrics.vridhi_avg_latency_ms` |
| **`baseline_source`** | `synthetic_noise_placeholder` | `baseline_source` |

> **Arithmetic note**: "Decision disagreements" (7 rows = 0.29 %) and
> "Disagreement rate" (0.0472 = 4.72 %) measure **different things**:
>
> - *Decision disagreements* counts rows where Vridhi and the noise proxy
>   land on opposite sides of the 0.5 high-risk threshold.
> - *Disagreement rate* counts rows where the absolute PD gap exceeds 0.25 —
>   a stricter, continuous measure of divergence from the synthetic proxy.
>
> Both figures are internally consistent.  The previous draft incorrectly
> listed `0.4930` as the disagreement rate alongside 95.07 % agreement —
> those two numbers are arithmetically incompatible.  The corrected figures
> (`0.0472` disagreement rate / 95.28 % agreement rate) are from the
> freshly regenerated run.

---

## 5. Governance Constraints (unchanged)

Structural properties, not runtime measurements:

- All score outputs carry `"recommended_action": "manual_review_required"`.
- No automated approve, decline, or pricing decision is possible.
- Climate severity, pincode, and UPI coverage are explicitly prohibited as
  sole adverse action reasons.
- Graph overlay is disabled by default and capped at ±3 pp.
- Automated model promotion is disabled; every candidate requires
  human risk-team sign-off (`PENDING_HUMAN_MODEL_RISK_APPROVAL`).

---

## 6. How to Reproduce

```powershell
$env:PYTHONPATH = "src"

# Step 1 — Generate synthetic reference dataset
python -m vridhi_sim.cli --output data/generated/reference

# Step 2 — Train model; records real wall-clock + Python-heap + process-RSS
python -m vridhi_sim.risk_cli --dataset data/generated/reference --output artifacts/risk/reference
# → artifacts/risk/reference/risk_engine_metadata.json.training_profile

# Step 3 — Shadow pilot with real full-scoring-path latency
python -m vridhi_sim.shadow_cli `
    --scores artifacts/risk/reference/research_scores.csv `
    --dataset data/generated/reference `
    --artifact-dir artifacts/risk/reference `
    --output artifacts/shadow/reference
# → artifacts/shadow/reference/shadow_pilot_report.json.latency_metrics.vridhi_avg_latency_ms

# Step 4 — Verify all tests pass
python -m pytest
```
