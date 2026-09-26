# Vridhi Analytics — Corrected ML Efficiency Report

> **Audit status**: This report was rewritten after a codebase audit identified fabricated
> efficiency numbers in a previous AI-generated draft.  All numbers below either trace
> directly to instrumented code or are explicitly labelled as unmeasured.
>
> **What changed**: Hardcoded latency literals (`14.2 ms`, `1200.0 ms`), an uncredited
> training-time claim (`~2.5 s`), and an ungrounded RAM figure (`<80 MB`) have been
> removed or replaced with real measurements.  The "vs Traditional Baseline Lender" framing
> has been corrected — the shadow comparison uses a synthetic noise-perturbed proxy, never a
> real lender or bank process.

---

## 1. Predictive Accuracy (verified, unchanged)

These numbers come directly from `risk_engine_metadata.json` and
`delayed_label_performance.json`, which are written by the training pipeline
using sklearn's `roc_auc_score`, `brier_score_loss`, and
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

## 2. Inference Latency (real measurement)

`evaluate_shadow_run()` now measures latency with `time.perf_counter()` inside
`ShadowPilotEngine._measure_vridhi_latency_ms()`.  The method performs
`_LATENCY_WARMUP_RUNS = 10` passes of the score-mapping and risk-band
classification path over the full sample, then reports the mean per-row
wall-clock time.

**What is measured**: the score-mapping and band-classification path
(the dominant hot path during a live scoring call).

**What is not measured**: model loading from disk, CSV I/O, feature
construction.  These are one-time or data-volume-dependent costs that belong
in a separate end-to-end profiling run.

| Measurement | Source | Value |
|:---|:---|:---|
| `vridhi_avg_latency_ms` | `time.perf_counter()` in `shadow_engine.py` | Varies by host; **run the shadow CLI to obtain your machine's figure** |
| `baseline_avg_latency_ms` | — | **Not measured** — no real lender inference process was available |

> The previous report claimed 14.2 ms (Vridhi) and 1,200 ms (baseline).
> Both were hardcoded literals with no connection to actual inference.
> They have been removed.

---

## 3. Training Duration & Memory (real measurement)

`risk_cli.py` now wraps the `RiskEngine.fit()` call with:

```python
tracemalloc.start()
t0 = time.perf_counter()
engine = RiskEngine(...).fit(rows)
train_wall_s = time.perf_counter() - t0
_, peak_bytes = tracemalloc.get_traced_memory()
tracemalloc.stop()
```

The measured values are written into `risk_engine_metadata.json` under the
`training_profile` key.  **Run `python -m vridhi_sim.risk_cli` to obtain
your machine's real figure.**

| Measurement | Source | Value |
|:---|:---|:---|
| `train_wall_clock_seconds` | `time.perf_counter()` in `risk_cli.py` | Stored in `risk_engine_metadata.json → training_profile` |
| `peak_memory_mb` | `tracemalloc` in `risk_cli.py` | Stored in `risk_engine_metadata.json → training_profile` |

> The previous report claimed "~2.5 s training" and "<80 MB RAM".
> Neither was grounded in any profiling code.  Both claims have been removed.

---

## 4. Shadow-Mode Pilot Concordance (vs synthetic noise baseline)

> [!WARNING]
> The shadow pilot was run **without a real lender baseline**.  The comparison
> partner is a **synthetic Gaussian noise-perturbed proxy** (`seed=42`,
> `σ = 0.15` applied to Vridhi PD).  This is an internal engineering sanity
> check, not a comparison against any real bank, NBFC, or credit bureau process.

The `shadow_pilot_report.json` now carries the explicit field:

```json
"baseline_source": "synthetic_noise_placeholder"
"baseline_note": "No real lender baseline was provided. ..."
```

| Metric | Value | Interpretation |
|:---|:---:|:---|
| **Total shadow evaluations** | 2,415 | All rows in reference dataset |
| **Agreement rate** | **95.07 %** | Fraction where Vridhi and noise-proxy agree on high-risk vs low-risk classification |
| **Disagreement rate** | 0.4930 | PD gap > 0.25 threshold |
| **Baseline source** | `synthetic_noise_placeholder` | **Not a real lender** |

> The previous report labelled this comparison "vs Traditional Baseline Lender"
> and cited a "98.8 % latency reduction" that was computed from a fabricated
> 1,200 ms baseline.  Both claims have been removed.

---

## 5. Governance Constraints (unchanged)

These are structural properties of the system, not runtime measurements:

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
# Generate synthetic reference dataset
$env:PYTHONPATH = "src"
python -m vridhi_sim.cli --output data/generated/reference

# Train model and record real wall-clock + memory
python -m vridhi_sim.risk_cli --dataset data/generated/reference --output artifacts/risk/reference
# → risk_engine_metadata.json.training_profile will contain your machine's real numbers

# Run shadow pilot (produces real latency measurement)
python -m vridhi_sim.shadow_cli --scores artifacts/risk/reference/research_scores.csv
# → shadow_pilot_report.json.latency_metrics.vridhi_avg_latency_ms will be measured

# Verify all tests pass
python -m pytest
```
