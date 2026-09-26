"""Configuration and public data contracts for the simulator."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path


@dataclass(frozen=True)
class RegionConfig:
    pincode: str
    district: str
    primary_crop: str
    crop_sale_months: tuple[int, ...] = (3, 4, 10, 11)
    baseline_crop_income: float = 22_000.0


@dataclass(frozen=True)
class SimulationConfig:
    """All parameters required to reproduce one scenario."""

    start_year: int = 2025
    months: int = 24
    farmers_per_region: int = 35
    retailers_per_region: int = 4
    wholesalers_per_region: int = 1
    seed: int = 42
    digital_share: float = 0.66
    monthly_loan_installment: float = 1_350.0
    output_dir: Path = Path("data/generated/reference")
    regions: tuple[RegionConfig, ...] = field(
        default_factory=lambda: (
            RegionConfig("413001", "Solapur", "soybean"),
            RegionConfig("431001", "Chhatrapati Sambhajinagar", "cotton"),
            RegionConfig("440001", "Nagpur", "paddy"),
        )
    )
