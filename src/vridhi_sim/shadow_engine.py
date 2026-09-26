"""Phase 9 Shadow-Mode Pilot Engine for non-intrusive credit decision validation.

Runs alongside existing lender underwriting processes, comparing recommendations
and measuring decision divergence without affecting real credit outcomes.
"""

from __future__ import annotations

import json
import time
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any, Sequence

import numpy as np
import pandas as pd
from sklearn.metrics import brier_score_loss, roc_auc_score

from .mlops import write_json

if TYPE_CHECKING:
    from .risk_engine import RiskEngine

# Number of repeated scoring passes used to estimate inference latency.
# A higher value averages out OS scheduling jitter; 5 is enough for warm XGBoost.
_LATENCY_WARMUP_RUNS = 5


@dataclass
class OfficerFeedback:
    score_id: str
    officer_id: str
    rating: int  # 1 to 5
    treeshap_helpful: bool
    comments: str
    timestamp: str


class ShadowPilotEngine:
    """Evaluates Vridhi model recommendations against baseline lender decisions."""

    def __init__(self, config_path: Path | None = None) -> None:
        self.config_path = config_path or Path("contracts/shadow_pilot_config.json")
        self.config = self._load_config()
        self.feedback_records: list[OfficerFeedback] = []

    def _load_config(self) -> dict[str, Any]:
        if self.config_path.exists():
            return json.loads(self.config_path.read_text(encoding="utf-8"))
        return {
            "version": "1.0.0",
            "shadow_mode_enabled": True,
            "disagreement_threshold_pd": 0.25,
            "min_sample_size": 10,
        }

    def record_feedback(self, feedback: OfficerFeedback) -> None:
        self.feedback_records.append(feedback)

    @staticmethod
    def _measure_real_scoring_latency_ms(
        risk_engine: "RiskEngine",
        sample_rows: list[dict[str, Any]],
    ) -> tuple[float, str]:
        """Measure per-row wall-clock latency of the full Vridhi scoring path.

        The full path includes:
          feature-matrix construction (_matrix) →
          XGBClassifier.predict_proba (base model) →
          LogisticRegression.predict_proba (Platt calibration) →
          per-row TreeSHAP explain() →
          risk-band classification and score-mapping

        This is what an actual live scoring call costs, not post-processing
        on an already-computed PD array.

        Returns
        -------
        avg_per_row_ms : float
            Mean per-row wall-clock time in milliseconds, averaged over
            _LATENCY_WARMUP_RUNS repeat passes.
        method_note : str
            Human-readable description of exactly what was timed.
        """
        n = max(len(sample_rows), 1)
        # One warm-up pass (discarded) to allow XGBoost's internal caches to settle.
        risk_engine.score(sample_rows)
        start = time.perf_counter()
        for _ in range(_LATENCY_WARMUP_RUNS):
            risk_engine.score(sample_rows)
        elapsed_s = time.perf_counter() - start
        avg_per_row_ms = (elapsed_s / (_LATENCY_WARMUP_RUNS * n)) * 1000.0
        method_note = (
            f"time.perf_counter() over {_LATENCY_WARMUP_RUNS} full scoring passes "
            f"on {n} rows (1 warm-up pass discarded). "
            "Covers: feature-matrix build, XGBClassifier.predict_proba, "
            "Platt-calibrator.predict_proba, per-row TreeSHAP explain(), "
            "risk-band classification, and score-mapping. "
            "Excludes: model load from disk and CSV I/O."
        )
        return round(avg_per_row_ms, 4), method_note

    def evaluate_shadow_run(
        self,
        scores_df: pd.DataFrame,
        labels_df: pd.DataFrame | None = None,
        lender_baseline_pd: Sequence[float] | None = None,
        risk_engine: "RiskEngine | None" = None,
        sample_rows: list[dict[str, Any]] | None = None,
    ) -> dict[str, Any]:
        """Compare Vridhi PD against baseline lender decisions or scores.

        Parameters
        ----------
        scores_df:
            DataFrame containing ``risk_pd`` column — the already-computed
            Vridhi PD scores for each row.
        labels_df:
            Optional DataFrame with ``repayment_status_30dpd`` column for
            computing performance divergence against ground truth.
        lender_baseline_pd:
            Actual lender PD scores for comparison.  When None, a synthetic
            noise-perturbed proxy is used and the report is labelled accordingly.
        risk_engine:
            A trained ``RiskEngine`` instance.  When provided together with
            ``sample_rows``, latency is measured over the **full scoring path**
            (feature build → XGBoost → calibration → TreeSHAP → band/score map).
            When None, latency is reported as null — the scoring path is not
            available in this evaluation context.
        sample_rows:
            The raw feature rows corresponding to ``scores_df``.  Required when
            ``risk_engine`` is provided.
        """
        n_samples = len(scores_df)
        if n_samples == 0:
            return {"status": "NO_DATA", "samples": 0}

        vridhi_pd = scores_df["risk_pd"].to_numpy()

        # --- Baseline determination ------------------------------------------
        if lender_baseline_pd is None:
            # Deterministic synthetic proxy — never a real lender process.
            rng = np.random.default_rng(42)
            baseline_pd = np.clip(vridhi_pd + rng.normal(0, 0.15, size=n_samples), 0.0, 1.0)
            baseline_source = "synthetic_noise_placeholder"
            baseline_note = (
                "No real lender baseline was provided.  "
                "The comparison uses a synthetic Gaussian-perturbed proxy (seed=42) "
                "and must not be presented as a real lender or bank benchmark."
            )
        else:
            baseline_pd = np.asarray(lender_baseline_pd, dtype=float)
            baseline_source = "real_lender_provided"
            baseline_note = "Baseline scores were supplied directly by the lender integration."

        # --- Decision agreement ----------------------------------------------
        disagreement = np.abs(vridhi_pd - baseline_pd) > self.config.get("disagreement_threshold_pd", 0.25)
        disagreement_rate = float(np.mean(disagreement))

        vridhi_high_risk = vridhi_pd >= 0.5
        baseline_declined = baseline_pd >= 0.5

        agreements = int(np.sum(vridhi_high_risk == baseline_declined))
        disagreements = int(n_samples - agreements)

        # --- Real scoring-path latency measurement ---------------------------
        if risk_engine is not None and sample_rows is not None:
            vridhi_avg_latency_ms, method_note = self._measure_real_scoring_latency_ms(
                risk_engine, sample_rows
            )
            latency_available = True
        else:
            vridhi_avg_latency_ms = None
            method_note = (
                "risk_engine was not provided to evaluate_shadow_run(); "
                "real scoring-path latency cannot be measured from a pre-computed "
                "PD array.  Pass risk_engine + sample_rows to obtain a real figure."
            )
            latency_available = False

        report: dict[str, Any] = {
            "generated_at": datetime.now(UTC).isoformat(),
            "status": "SHADOW_PILOT_COMPLETED",
            "total_evaluations": n_samples,
            "disagreement_rate": round(disagreement_rate, 4),
            "baseline_source": baseline_source,
            "baseline_note": baseline_note,
            "decision_matrix": {
                "agreements": agreements,
                "disagreements": disagreements,
                "vridhi_high_lender_approve": int(np.sum(vridhi_high_risk & ~baseline_declined)),
                "vridhi_low_lender_decline": int(np.sum(~vridhi_high_risk & baseline_declined)),
            },
            "latency_metrics": {
                "vridhi_avg_latency_ms": vridhi_avg_latency_ms,
                "latency_path_complete": latency_available,
                "latency_measurement_method": method_note,
                # Baseline latency is not measured — no real lender inference process available.
                "baseline_avg_latency_ms": None,
                "baseline_latency_note": (
                    "Not measured.  No real lender inference process was available "
                    "during this shadow pilot run."
                ),
            },
        }

        # --- Performance divergence (only when real labels present) ----------
        if labels_df is not None and "repayment_status_30dpd" in labels_df.columns:
            y_true = labels_df["repayment_status_30dpd"].to_numpy()
            if len(np.unique(y_true)) > 1:
                vridhi_auc = float(roc_auc_score(y_true, vridhi_pd))
                baseline_auc = float(roc_auc_score(y_true, baseline_pd))
                vridhi_brier = float(brier_score_loss(y_true, vridhi_pd))
                baseline_brier = float(brier_score_loss(y_true, baseline_pd))

                report["label_ground_truth"] = {
                    "vridhi_roc_auc": round(vridhi_auc, 4),
                    "baseline_roc_auc": round(baseline_auc, 4),
                    "baseline_label": baseline_source,
                    "auc_improvement_vs_baseline": round(vridhi_auc - baseline_auc, 4),
                    "vridhi_brier": round(vridhi_brier, 4),
                    "baseline_brier": round(baseline_brier, 4),
                }

        # --- Officer feedback summary ----------------------------------------
        if self.feedback_records:
            ratings = [f.rating for f in self.feedback_records]
            helpful_cnt = sum(1 for f in self.feedback_records if f.treeshap_helpful)
            report["operational_feedback_summary"] = {
                "total_feedbacks": len(ratings),
                "average_rating": round(float(np.mean(ratings)), 2),
                "treeshap_usefulness_pct": round(helpful_cnt / len(ratings), 4),
            }
        else:
            report["operational_feedback_summary"] = {
                "total_feedbacks": 0,
                "average_rating": 0.0,
                "treeshap_usefulness_pct": 0.0,
            }

        return report

    def save_report(self, report: dict[str, Any], output_path: Path) -> None:
        write_json(output_path, report)
