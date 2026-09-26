"""A small, reproducible causal simulator for the Vridhi research dataset."""

from __future__ import annotations

import csv
import json
import random
from collections import defaultdict
from dataclasses import asdict
from datetime import datetime
from pathlib import Path
from statistics import fmean, pstdev
from typing import Iterable

from .config import SimulationConfig
from .entities import Agent, ClimateShock, Farmer


class MicroEconomySimulator:
    """Simulates monthly flows without using real identities or transactions.

    The important invariant is point-in-time causality: an event is calculated
    only from agent state and shocks known in that month. Future outcomes never
    affect an earlier transaction or feature.
    """

    def __init__(self, config: SimulationConfig, shocks: Iterable[ClimateShock] = ()):
        self.config = config
        self.rng = random.Random(config.seed)
        self.shocks = {(s.year, s.month, s.pincode): s.drought_severity for s in shocks}
        self.agents: dict[str, Agent] = {}
        self.region_agents: dict[str, dict[str, list[str] | str]] = {}
        self.nodes: list[dict[str, object]] = []
        self.edges: list[dict[str, object]] = []
        self.snapshots: list[dict[str, object]] = []
        self.labels: list[dict[str, object]] = []
        self._period_income: defaultdict[str, float] = defaultdict(float)
        self._period_expense: defaultdict[str, float] = defaultdict(float)

    @staticmethod
    def load_climate_shocks(path: Path) -> list[ClimateShock]:
        """Load the stable adapter contract used by approved external data feeds."""
        shocks: list[ClimateShock] = []
        with path.open(newline="", encoding="utf-8") as handle:
            required = {"year", "month", "pincode", "drought_severity"}
            reader = csv.DictReader(handle)
            if not reader.fieldnames or not required.issubset(reader.fieldnames):
                raise ValueError(f"Climate CSV must contain: {', '.join(sorted(required))}")
            for row in reader:
                severity = float(row["drought_severity"])
                if not 0.0 <= severity <= 1.0:
                    raise ValueError("drought_severity must be within [0, 1]")
                month = int(row["month"])
                if not 1 <= month <= 12:
                    raise ValueError("month must be within [1, 12]")
                shocks.append(ClimateShock(int(row["year"]), month, row["pincode"], severity))
        return shocks

    def _add_agent(self, agent: Agent, **attributes: object) -> None:
        self.agents[agent.entity_id] = agent
        self.nodes.append(
            {
                "entity_id": agent.entity_id,
                "entity_type": agent.entity_type,
                "pincode": agent.pincode,
                "synthetic": True,
                **attributes,
            }
        )

    def _create_agents(self) -> None:
        if self.agents:
            return
        self._add_agent(Agent("lender:vridhi", "synthetic_lender", "national", 2_000_000.0))
        for region in self.config.regions:
            utility_id = f"utility:{region.pincode}"
            self._add_agent(Agent(utility_id, "utility_company", region.pincode, 300_000.0))
            wholesalers: list[str] = []
            for index in range(self.config.wholesalers_per_region):
                entity_id = f"wholesaler:{region.pincode}:{index + 1:02d}"
                # Wholesalers need working capital large enough to buy a regional
                # harvest before downstream retailer replenishment arrives.
                self._add_agent(Agent(entity_id, "wholesaler", region.pincode, 2_000_000.0))
                wholesalers.append(entity_id)
            retailers: list[str] = []
            for index in range(self.config.retailers_per_region):
                entity_id = f"retailer:{region.pincode}:{index + 1:02d}"
                self._add_agent(Agent(entity_id, "kirana", region.pincode, 80_000.0))
                retailers.append(entity_id)
            farmers: list[str] = []
            for index in range(self.config.farmers_per_region):
                entity_id = f"farmer:{region.pincode}:{index + 1:03d}"
                irrigation = round(self.rng.uniform(0.05, 0.85), 3)
                land = round(self.rng.uniform(0.6, 3.2), 2)
                farmer = Farmer(
                    entity_id=entity_id,
                    entity_type="farmer",
                    pincode=region.pincode,
                    cash_balance=self.rng.uniform(16_000.0, 52_000.0),
                    crop=region.primary_crop,
                    irrigation_resilience=irrigation,
                    land_hectares=land,
                    baseline_crop_income=region.baseline_crop_income,
                    crop_sale_months=region.crop_sale_months,
                )
                self._add_agent(
                    farmer,
                    crop=farmer.crop,
                    irrigation_resilience=farmer.irrigation_resilience,
                    land_hectares=farmer.land_hectares,
                )
                farmers.append(entity_id)
            self.region_agents[region.pincode] = {
                "utility": utility_id,
                "wholesalers": wholesalers,
                "retailers": retailers,
                "farmers": farmers,
            }

    def _transfer(
        self,
        year: int,
        month: int,
        payer_id: str,
        payee_id: str,
        amount: float,
        transaction_type: str,
        drought_severity: float,
        probability_digital: float | None = None,
    ) -> float:
        """Apply a payment and export an edge only when it is digitally observed."""
        payer = self.agents[payer_id]
        payee = self.agents[payee_id]
        paid = round(min(max(amount, 0.0), max(payer.cash_balance, 0.0)), 2)
        if not paid:
            return 0.0
        payer.cash_balance -= paid
        payee.cash_balance += paid
        self._period_expense[payer_id] += paid
        self._period_income[payee_id] += paid
        digital_probability = probability_digital if probability_digital is not None else self.config.digital_share
        if self.rng.random() <= digital_probability:
            timestamp = datetime(year, month, 1).isoformat() + "Z"
            self.edges.append(
                {
                    "event_id": f"tx-{year}{month:02d}-{len(self.edges) + 1:08d}",
                    "timestamp": timestamp,
                    "source_id": payer_id,
                    "target_id": payee_id,
                    "amount_inr": paid,
                    "transaction_type": transaction_type,
                    "channel": "upi",
                    "pincode": payer.pincode,
                    "drought_severity": drought_severity,
                    "synthetic": True,
                }
            )
        return paid

    def _run_month(self, year: int, month: int) -> None:
        self._period_income.clear()
        self._period_expense.clear()
        for region in self.config.regions:
            group = self.region_agents[region.pincode]
            severity = self.shocks.get((year, month, region.pincode), 0.0)
            wholesaler_id = self.rng.choice(group["wholesalers"])  # type: ignore[arg-type]

            # A drought affects crop proceeds, not a borrower's score directly.
            for farmer_id in group["farmers"]:  # type: ignore[union-attr]
                farmer = self.agents[farmer_id]
                assert isinstance(farmer, Farmer)
                if month in farmer.crop_sale_months:
                    yield_factor = max(0.18, 1.0 - severity * (1.0 - 0.68 * farmer.irrigation_resilience))
                    price_factor = self.rng.uniform(0.86, 1.14)
                    sale = (
                        farmer.baseline_crop_income
                        * farmer.land_hectares
                        * yield_factor
                        * price_factor
                        / len(farmer.crop_sale_months)
                    )
                    self._transfer(year, month, wholesaler_id, farmer_id, sale, "crop_sale", severity, 0.78)

                retailer_id = self.rng.choice(group["retailers"])  # type: ignore[arg-type]
                essentials = self.rng.uniform(1_450.0, 3_150.0)
                self._transfer(year, month, farmer_id, retailer_id, essentials, "kirana_purchase", severity)

                utility_due = 420.0 + (210.0 if farmer.irrigation_resilience > 0.45 else 85.0)
                paid_utility = self._transfer(
                    year, month, farmer_id, group["utility"], utility_due, "utility_payment", severity, 0.69  # type: ignore[arg-type]
                )
                if paid_utility < utility_due * 0.98:
                    farmer.missed_utility_payments += 1

                installment = self.config.monthly_loan_installment
                paid_installment = self._transfer(
                    year, month, farmer_id, "lender:vridhi", installment, "loan_repayment", severity, 0.82
                )
                farmer.overdue_installments = max(0, farmer.overdue_installments - 1) if paid_installment >= installment * 0.98 else farmer.overdue_installments + 1

            # Kiranas replenish after monthly sales; this creates the farmer-retailer-wholesaler path.
            for retailer_id in group["retailers"]:  # type: ignore[union-attr]
                retailer = self.agents[retailer_id]
                restock = self._period_income[retailer_id] * self.rng.uniform(0.50, 0.70)
                self._transfer(year, month, retailer_id, wholesaler_id, restock, "retailer_restock", severity, 0.74)
                self._transfer(year, month, retailer_id, group["utility"], 1_050.0, "utility_payment", severity, 0.78)  # type: ignore[arg-type]

            # Wholesaler operating utilities are part of the same local graph.
            self._transfer(year, month, wholesaler_id, group["utility"], 2_400.0, "utility_payment", severity, 0.80)  # type: ignore[arg-type]

        self._capture_month(year, month)

    def _capture_month(self, year: int, month: int) -> None:
        timestamp = datetime(year, month, 1).date().isoformat()
        for agent in self.agents.values():
            income = round(self._period_income[agent.entity_id], 2)
            expense = round(self._period_expense[agent.entity_id], 2)
            agent.monthly_income.append(income)
            agent.monthly_expense.append(expense)
            trailing_income = agent.monthly_income[-3:]
            volatility = pstdev(trailing_income) / max(fmean(trailing_income), 1.0) if len(trailing_income) > 1 else 0.0
            severity = self.shocks.get((year, month, agent.pincode), 0.0)
            repayment_ability = 0.0
            if agent.entity_type == "farmer":
                repayment_ability = min(2.0, max(0.0, (agent.cash_balance + max(income - expense, 0.0)) / self.config.monthly_loan_installment))
            self.snapshots.append(
                {
                    "month": timestamp,
                    "entity_id": agent.entity_id,
                    "entity_type": agent.entity_type,
                    "pincode": agent.pincode,
                    "cash_balance": round(agent.cash_balance, 2),
                    "income_inr": income,
                    "expense_inr": expense,
                    "net_cash_flow_inr": round(income - expense, 2),
                    "income_volatility_3m": round(volatility, 4),
                    "missed_utility_payments": agent.missed_utility_payments,
                    "overdue_installments": agent.overdue_installments,
                    "drought_severity": severity,
                    "repayment_ability_proxy": round(repayment_ability, 4),
                    "synthetic": True,
                }
            )
            if agent.entity_type == "farmer":
                self.labels.append(
                    {
                        "month": timestamp,
                        "farmer_id": agent.entity_id,
                        "pincode": agent.pincode,
                        "synthetic_30dpd": int(agent.overdue_installments >= 1),
                        "synthetic_60dpd": int(agent.overdue_installments >= 2),
                        "repayment_ability_proxy": round(repayment_ability, 4),
                        "drought_severity": severity,
                        "label_origin": "simulator_rule_not_real_credit_outcome",
                    }
                )

    def run(self) -> "MicroEconomySimulator":
        self._create_agents()
        for step in range(self.config.months):
            year = self.config.start_year + step // 12
            month = step % 12 + 1
            self._run_month(year, month)
        return self

    @staticmethod
    def _write_csv(path: Path, rows: list[dict[str, object]]) -> None:
        if not rows:
            return
        # Graph node types legitimately have different attributes. Preserve the
        # full schema rather than silently dropping farmer-specific fields.
        fieldnames = list(dict.fromkeys(field for row in rows for field in row))
        with path.open("w", newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(handle, fieldnames=fieldnames, extrasaction="raise")
            writer.writeheader()
            writer.writerows(rows)

    def export(self, output_dir: Path | None = None) -> Path:
        if not self.snapshots:
            raise RuntimeError("Run the simulation before exporting it.")
        destination = Path(output_dir or self.config.output_dir)
        destination.mkdir(parents=True, exist_ok=True)
        self._write_csv(destination / "nodes.csv", self.nodes)
        self._write_csv(destination / "edges.csv", self.edges)
        self._write_csv(destination / "node_month.csv", self.snapshots)
        self._write_csv(destination / "borrower_month_labels.csv", self.labels)
        summary = {
            "schema_version": "1.0",
            "synthetic_only": True,
            "seed": self.config.seed,
            "months": self.config.months,
            "agents": len(self.nodes),
            "upi_edges": len(self.edges),
            "farmer_month_labels": len(self.labels),
            "drought_observations": len(self.shocks),
            "farmers_with_any_synthetic_30dpd": len({r["farmer_id"] for r in self.labels if r["synthetic_30dpd"]}),
            "configuration": {**asdict(self.config), "output_dir": str(self.config.output_dir)},
            "limitations": [
                "Synthetic repayment labels are simulation rules, not observed credit outcomes.",
                "UPI edges are an observed subset; other simulated payments may be cash.",
                "Climate input requires provenance and spatial validation before production use.",
            ],
        }
        with (destination / "scenario_summary.json").open("w", encoding="utf-8") as handle:
            json.dump(summary, handle, indent=2, default=str)
        return destination
