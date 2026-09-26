"""Split loan_applications_faculty_demo.csv into 10 dedicated isolated bank node CSV files and generate configs."""

import csv
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MASTER_CSV = ROOT / "data" / "loan_applications_faculty_demo.csv"

# Configuration for 10 distinct Indian commercial & regional bank server nodes
BANK_DEFINITIONS = [
    {
        "code": "sbi",
        "bank_code": "SBIN",
        "bank_name": "State Bank of India",
        "node_id": "sbi-risk-node-01",
        "port": 8001,
        "branch_pin": "413001",
        "officer_roles": ["OFFICER-789", "SBIN-OFFICER-101", "SBIN-UNDERWRITER-01"]
    },
    {
        "code": "mahb",
        "bank_code": "MAHB",
        "bank_name": "Bank of Maharashtra",
        "node_id": "mahb-risk-node-02",
        "port": 8002,
        "branch_pin": "413002",
        "officer_roles": ["OFFICER-789", "MAHB-OFFICER-101", "MAHB-UNDERWRITER-01"]
    },
    {
        "code": "cbin",
        "bank_code": "CBIN",
        "bank_name": "Central Bank of India",
        "node_id": "cbin-risk-node-03",
        "port": 8003,
        "branch_pin": "413003",
        "officer_roles": ["OFFICER-789", "CBIN-OFFICER-101", "CBIN-UNDERWRITER-01"]
    },
    {
        "code": "bob",
        "bank_code": "BARB",
        "bank_name": "Bank of Baroda",
        "node_id": "bob-risk-node-04",
        "port": 8004,
        "branch_pin": "413004",
        "officer_roles": ["OFFICER-789", "BARB-OFFICER-101", "BARB-UNDERWRITER-01"]
    },
    {
        "code": "pnb",
        "bank_code": "PUNB",
        "bank_name": "Punjab National Bank",
        "node_id": "pnb-risk-node-05",
        "port": 8005,
        "branch_pin": "413005",
        "officer_roles": ["OFFICER-789", "PUNB-OFFICER-101", "PUNB-UNDERWRITER-01"]
    },
    {
        "code": "ubi",
        "bank_code": "UBIN",
        "bank_name": "Union Bank of India",
        "node_id": "ubi-risk-node-06",
        "port": 8006,
        "branch_pin": "413006",
        "officer_roles": ["OFFICER-789", "UBIN-OFFICER-101", "UBIN-UNDERWRITER-01"]
    },
    {
        "code": "canara",
        "bank_code": "CNRB",
        "bank_name": "Canara Bank",
        "node_id": "canara-risk-node-07",
        "port": 8007,
        "branch_pin": "413007",
        "officer_roles": ["OFFICER-789", "CNRB-OFFICER-101", "CNRB-UNDERWRITER-01"]
    },
    {
        "code": "mgb",
        "bank_code": "MAHG",
        "bank_name": "Maharashtra Gramin Bank",
        "node_id": "mgb-risk-node-08",
        "port": 8008,
        "branch_pin": "413008",
        "officer_roles": ["OFFICER-789", "MAHG-OFFICER-101", "MAHG-UNDERWRITER-01"]
    },
    {
        "code": "icici",
        "bank_code": "ICIC",
        "bank_name": "ICICI Rural Bank",
        "node_id": "icici-risk-node-09",
        "port": 8009,
        "branch_pin": "413009",
        "officer_roles": ["OFFICER-789", "ICIC-OFFICER-101", "ICIC-UNDERWRITER-01"]
    },
    {
        "code": "hdfc",
        "bank_code": "HDFC",
        "bank_name": "HDFC Rural Bank",
        "node_id": "hdfc-risk-node-10",
        "port": 8010,
        "branch_pin": "413010",
        "officer_roles": ["OFFICER-789", "HDFC-OFFICER-101", "HDFC-UNDERWRITER-01"]
    }
]


def split_datasets():
    if not MASTER_CSV.exists():
        print(f"Master CSV not found at {MASTER_CSV}")
        return

    with MASTER_CSV.open("r", encoding="utf-8") as f:
        reader = list(csv.DictReader(f))

    fieldnames = list(reader[0].keys())

    for bank in BANK_DEFINITIONS:
        code = bank["code"]
        bank_name = bank["bank_name"]
        node_dir = ROOT / "servers" / f"{code}_node"
        node_dir.mkdir(parents=True, exist_ok=True)

        # 1. Filter rows for this bank
        bank_rows = [r for r in reader if r.get("bank_name").strip().lower() == bank_name.strip().lower()]

        # Fallback to dynamic split if no exact rows found
        if not bank_rows:
            # Distribute data roughly equally using port modulo
            idx_offset = bank["port"] % 10
            bank_rows = reader[idx_offset::10]

        csv_filename = f"{code}_applications.csv"
        csv_path = node_dir / csv_filename

        with csv_path.open("w", encoding="utf-8", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(bank_rows)

        # 2. Generate config.json dynamically
        config = {
            "bank_code": bank["bank_code"],
            "bank_name": bank["bank_name"],
            "node_id": bank["node_id"],
            "port": bank["port"],
            "data_file": f"servers/{code}_node/{csv_filename}",
            "officer_roles": bank["officer_roles"],
            "branch_pin": bank["branch_pin"],
            "risk_policy": {
                "max_risk_pd": 0.25,
                "min_credit_score": 600,
                "agri_bonus_pct": 0.05
            }
        }

        config_path = node_dir / "config.json"
        with config_path.open("w", encoding="utf-8") as f:
            json.dump(config, f, indent=2)

        print(f"Successfully generated {code}_node directory structure with {len(bank_rows)} isolated records.")


if __name__ == "__main__":
    split_datasets()
