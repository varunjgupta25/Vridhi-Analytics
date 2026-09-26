"""Command-line entry point for reference scenarios."""

from __future__ import annotations

import argparse
from pathlib import Path

from .config import SimulationConfig
from .simulator import MicroEconomySimulator


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate Vridhi's synthetic temporal graph dataset.")
    parser.add_argument("--output", type=Path, default=Path("data/generated/reference"))
    parser.add_argument("--months", type=int, default=24)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--climate-shocks", type=Path, help="CSV using the documented climate adapter schema")
    args = parser.parse_args()
    if args.months < 1:
        parser.error("--months must be positive")
    shocks = MicroEconomySimulator.load_climate_shocks(args.climate_shocks) if args.climate_shocks else []
    simulation = MicroEconomySimulator(
        SimulationConfig(months=args.months, seed=args.seed, output_dir=args.output), shocks
    ).run()
    output = simulation.export()
    print(f"Generated synthetic temporal graph dataset in {output.resolve()}")


if __name__ == "__main__":
    main()
