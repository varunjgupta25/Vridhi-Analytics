"""Internal agent representations. These are synthetic and contain no PII."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class Agent:
    entity_id: str
    entity_type: str
    pincode: str
    cash_balance: float
    monthly_income: list[float] = field(default_factory=list)
    monthly_expense: list[float] = field(default_factory=list)
    overdue_installments: int = 0
    missed_utility_payments: int = 0


@dataclass
class Farmer(Agent):
    crop: str = ""
    irrigation_resilience: float = 0.0
    land_hectares: float = 1.0
    baseline_crop_income: float = 0.0
    crop_sale_months: tuple[int, ...] = ()


@dataclass(frozen=True)
class ClimateShock:
    year: int
    month: int
    pincode: str
    drought_severity: float
