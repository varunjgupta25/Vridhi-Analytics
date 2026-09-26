"""Generate comprehensive faculty demo CSV containing 105 unique rural entrepreneur applications with 100% unique IFSC codes, account numbers, and financial details."""

from __future__ import annotations

import csv
import json
import random
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCORES_FILE = ROOT / "artifacts" / "risk" / "reference" / "research_scores.csv"
NODES_FILE = ROOT / "data" / "generated" / "reference" / "nodes.csv"
NODE_MONTH_FILE = ROOT / "data" / "generated" / "reference" / "node_month.csv"
OUTPUT_CSV = ROOT / "data" / "loan_applications_faculty_demo.csv"

BANKS = [
    ("State Bank of India", "SBIN00"),
    ("Bank of Maharashtra", "MAHB00"),
    ("Central Bank of India", "CBIN00"),
    ("Bank of Baroda", "BARB00"),
    ("Punjab National Bank", "PUNB00"),
    ("Maharashtra Gramin Bank", "MAHG00"),
    ("Union Bank of India", "UBIN00"),
    ("Canara Bank", "CNRB00"),
    ("HDFC Rural Bank", "HDFC00"),
    ("ICICI Rural Bank", "ICIC00"),
]

BRANCHES = {
    "413001": ["Barshi Main Branch, Solapur", "Vairag Rural Branch", "Kurduwadi Branch", "Solapur Enterprise Branch"],
    "431001": ["Paithan Main Branch, Sambhajinagar", "Shevgaon Road Branch", "Sambhajinagar MSME Branch"],
    "440001": ["Kamptee Main Branch, Nagpur", "Hingna Industrial Branch", "Nagpur Rural West Branch"],
}

RURAL_ENTERPRISES = [
    ("no", "Non-Agri Micro-Enterprise", "Kirana & General Store", 5, "Owned Commercial Premises", "High (50+ transactions/day)", 0.0, ""),
    ("no", "Non-Agri Micro-Enterprise", "Dairy & Milk Collection Unit", 4, "Leased / Rented Shop", "High (50+ transactions/day)", 0.0, ""),
    ("no", "Non-Agri Micro-Enterprise", "Agri-Input & Seed Dealer", 6, "Owned Commercial Premises", "Moderate (20-50/day)", 0.0, ""),
    ("yes", "Agricultural / Farming", "Soybean & Cotton Farm Enterprise", 0, "", "", 4.5, "Drip Irrigation / Well"),
    ("no", "Non-Agri Micro-Enterprise", "Spices & Food Processing Unit", 3, "Leased / Rented Shop", "Moderate (20-50/day)", 0.0, ""),
    ("no", "Non-Agri Micro-Enterprise", "Tractor & Machinery Rental", 7, "Owned Commercial Premises", "High (50+ transactions/day)", 0.0, ""),
    ("no", "Non-Agri Micro-Enterprise", "Rural Solar & Electricals", 2, "Leased / Rented Shop", "Moderate (20-50/day)", 0.0, ""),
    ("yes", "Agricultural / Farming", "Paddy & Sugarcane Enterprise", 0, "", "", 6.0, "Solar Pump System"),
    ("no", "Non-Agri Micro-Enterprise", "Handloom & Textile Enterprise", 4, "Home-based / Mobile", "Moderate (20-50/day)", 0.0, ""),
    ("no", "Non-Agri Micro-Enterprise", "Rural Transport & Logistics", 5, "Owned Commercial Premises", "High (50+ transactions/day)", 0.0, ""),
    ("yes", "Agricultural / Farming", "Pomegranate & Fruit Farm", 0, "", "", 3.5, "Drip Irrigation / Well"),
    ("no", "Non-Agri Micro-Enterprise", "Poultry & Hatchery Farm", 3, "Owned Commercial Premises", "Moderate (20-50/day)", 0.0, ""),
]

UNIQUE_NAMES = [
    "Ramesh Pawar", "Meera Jadhav", "Sunita Borse", "Vijay Patil", "Anil Deshmukh",
    "Pooja Shinde", "Sanjay Kulkarni", "Ganesh More", "Priya Rathod", "Rajesh Gaikwad",
    "Santosh Chavan", "Kavita Jagtap", "Prakash Kadam", "Balasaheb Joshi", "Archana Bhosale",
    "Dnyaneshwar Salunkhe", "Pandurang Waghmare", "Eknath Mane", "Ashok Kambale", "Suresh Shelke",
    "Baban Phadke", "Vitthal Garad", "Maroti Solanke", "Shankar Wagh", "Narayan Nikam",
    "Nitin Salunke", "Sachin Thorat", "Rahul Gite", "Vikas Landge", "Amol Gade",
    "Sandip Giram", "Mahesh Mule", "Devidas Dake", "Sunil Kakade", "Datta Nagre",
    "Dipak Bangar", "Popat Sanap", "Sopan Avhad", "Haribhau Bodkhe", "Bhaskar Khedkar",
    "Babasaheb Kute", "Raosaheb Mungase", "Sudam Ghuge", "Shrimant Auti", "Vishnu Dahiphale",
    "Ramdas Palve", "Tukaram Darade", "Madhukar Khose", "Dinkar Hande", "Bhagwan Tidke",
    "Arjun Bhagat", "Laxman Mhaske", "Chhabu Gawande", "Sampat Ghodke", "Dattatraya Lande",
    "Ranganath Kakade", "Machhindra Shelke", "Navnath Borude", "Gorakhnath Temkar", "Somnath Walunj",
    "Adinath Pawashe", "Kashinath Dhage", "Trimbak Misal", "Sadashiv Sanap", "Changdeo Gadekar",
    "Sopanrao Khedkar", "Anandrao Popalghat", "Ganpatrao Sonawane", "Bhausaheb Tambe", "Nivrutti Hase",
    "Pandharinath Dushing", "Yashwant Gunjal", "Jaywant Kolhe", "Hanumant Zaware", "Shrikant Rohokale",
    "Somashekhar Bhingarde", "Babanrao Nawale", "Sharadrao Landge", "Prabhakar Shedge", "Chandrakant Thorat",
    "Digambar Shinde", "Uttamrao Borhade", "Janardan Gunjal", "Gulabrao Kawade", "Subhashrao Belhekar",
    "Namdeorao Kardile", "Uttam Kharde", "Sahebrao Kotkar", "Raosaheb Londhe", "Kisanrao Farakte",
    "Damodar Mhaske", "Jagannath Pachpute", "Narayanrao Shelke", "Popatrao Varpe", "Raghunath Walunj",
    "Sakharam Zende", "Tarachand Gite", "Vithalrao Kakade", "Wamanrao Lande", "Yamunaji Mule",
    "Madhavrao Nagre", "Narsing Palve", "Parashram Sanap", "Radhakishan Tidke", "Sampatrao Zaware"
]


def generate_demo_csv() -> None:
    random.seed(42)

    farmers = []
    if NODES_FILE.exists():
        with NODES_FILE.open("r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                if row.get("entity_type") == "farmer":
                    farmers.append(row)

    scores_by_farmer = {}
    if SCORES_FILE.exists():
        with SCORES_FILE.open("r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                fid = row["farmer_id"]
                scores_by_farmer[fid] = row

    features_by_farmer = {}
    if NODE_MONTH_FILE.exists():
        with NODE_MONTH_FILE.open("r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                fid = row.get("node_id", "")
                if fid.startswith("farmer:"):
                    features_by_farmer[fid] = row

    rows_to_write = []
    target_list = farmers if farmers else [{"entity_id": f"farmer:413001:{i:03d}", "pincode": "413001"} for i in range(1, 106)]

    for idx, farmer in enumerate(target_list[:105], start=1):
        fid = farmer["entity_id"]
        pincode = str(farmer.get("pincode", "413001"))
        
        is_agri, sector, enterprise, vintage, premises, footfall, land, irrigation = RURAL_ENTERPRISES[(idx - 1) % len(RURAL_ENTERPRISES)]

        bank_name, ifsc_prefix = BANKS[(idx - 1) % len(BANKS)]
        branch_list = BRANCHES.get(pincode, ["Enterprise Branch"])
        branch_name = branch_list[(idx - 1) % len(branch_list)]

        bank_code = ifsc_prefix[:4]
        account_number = f"{bank_code}{pincode}{idx:03d}"
        
        # 100% Unique 11-Character IFSC Code for every single applicant
        ifsc_code = f"{bank_code}0{pincode[:3]}{idx:03d}"

        borrower_name = UNIQUE_NAMES[idx - 1] if idx <= len(UNIQUE_NAMES) else f"Borrower {idx}"

        feat_rec = features_by_farmer.get(fid, {})
        income = float(feat_rec.get("income_inr", 38000 + (idx * 637) % 45000)) + ((idx * 11) % 850)
        expense = float(feat_rec.get("expense_inr", 24000 + (idx * 419) % 28000)) + ((idx * 7) % 420)
        cash = float(feat_rec.get("cash_balance", 9000 + (idx * 1231) % 35000)) + ((idx * 13) % 910)
        missed_util = int(float(feat_rec.get("missed_utility_payments", 0)))
        overdue_inst = int(float(feat_rec.get("overdue_installments", 0)))
        drought = float(feat_rec.get("drought_severity", 0.2))

        # Payment History Metrics with Unique Variations per Row
        if overdue_inst == 0 and missed_util == 0:
            on_time_pct = 94 + (idx % 6)
            nach_bounces = 0
            avg_delay = round(((idx % 5) * 0.2), 1)
            dpd_trail = "0-0-0-0-0-0-0-0-0-0-0-0"
            compliance_pct = 95 + (idx % 5)
            credit_util = 22 + (idx * 3) % 32
        elif overdue_inst == 1 or missed_util == 1:
            on_time_pct = 82 - (idx % 6)
            nach_bounces = 1
            avg_delay = round(3.5 + (idx % 4) * 0.5, 1)
            dpd_trail = "0-0-30-0-0-0-0-30-0-0-0-0"
            compliance_pct = 78 - (idx % 5)
            credit_util = 60 + (idx * 2) % 22
        else:
            on_time_pct = 64 - (idx % 10)
            nach_bounces = 2 + (idx % 2)
            avg_delay = round(11.0 + (idx % 6) * 0.8, 1)
            dpd_trail = "0-0-30-0-60-30-0-0-30-0-60-30"
            compliance_pct = 56 - (idx % 7)
            credit_util = 82 + (idx % 15)

        agri_flag = is_agri == "yes"
        agri_bonus = -0.05 if (agri_flag and ("Solar" in irrigation or "Drip" in irrigation)) else 0.0
        vintage_bonus = -0.04 if (not agri_flag and isinstance(vintage, int) and vintage >= 3) else 0.0
        behavior_penalty = (100 - on_time_pct) * 0.003 + (nach_bounces * 0.04)

        risk_pd = max(0.02, min(0.95, 0.05 + (drought * 0.30) + (missed_util * 0.06) + (overdue_inst * 0.10) - (cash / max(1000.0, income * 2.0)) * 0.08 + agri_bonus + vintage_bonus + behavior_penalty))
        score = max(300, min(900, int(850 - risk_pd * 600)))
        risk_pd_pct = f"{risk_pd * 100:.1f}%"
        risk_band = "Low" if risk_pd < 0.15 else ("Moderate" if risk_pd < 0.30 else "High")

        app_id = f"APP-2026-{idx:03d}"
        timestamp = f"2026-08-05T{10 + (idx % 8):02d}:{(idx * 7) % 60:02d}:{(idx * 13) % 60:02d}Z"

        if risk_band == "High":
            rec_step = "High credit/payment delinquency stress. Conduct mandatory underwriter review before loan renewal."
        elif risk_band == "Moderate":
            rec_step = "Conduct in-person business check to verify GST/trade receipts and inventory turnover."
        else:
            rec_step = "Standard review approved. High payment punctuality trail verified."

        rows_to_write.append({
            "application_id": app_id,
            "timestamp": timestamp,
            "bank_name": bank_name,
            "branch_name": branch_name,
            "account_number": account_number,
            "ifsc_code": ifsc_code,
            "borrower_name": borrower_name,
            "pincode": pincode,
            "is_agri_enterprise": is_agri,
            "enterprise_sector": sector,
            "enterprise_type": enterprise,
            "crop_type": enterprise,
            "business_vintage_years": vintage if is_agri == "no" else "",
            "premises_status": premises if is_agri == "no" else "",
            "customer_footfall": footfall if is_agri == "no" else "",
            "land_acres": land if is_agri == "yes" else "",
            "irrigation_type": irrigation if is_agri == "yes" else "",
            "monthly_income_inr": f"{income:.2f}",
            "monthly_expense_inr": f"{expense:.2f}",
            "cash_balance_inr": f"{cash:.2f}",
            "missed_utility_bills": missed_util,
            "overdue_installments": overdue_inst,
            "drought_severity": f"{drought:.2f}",
            "on_time_payment_pct_24m": f"{on_time_pct}%",
            "dpd_trail_12m": dpd_trail,
            "nach_bounces_12m": nach_bounces,
            "avg_payment_delay_days": f"{avg_delay:.1f}",
            "bbps_utility_compliance_pct": f"{compliance_pct}%",
            "credit_utilization_pct": f"{credit_util}%",
            "synthetic_credit_score": score,
            "risk_pd_pct": risk_pd_pct,
            "risk_band": risk_band,
            "recommended_action": rec_step,
            "policy_decision": "MANUAL_REVIEW_REQUIRED"
        })

    OUTPUT_CSV.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = list(rows_to_write[0].keys())
    with OUTPUT_CSV.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows_to_write)

    print(f"Faculty Demo CSV updated with {len(rows_to_write)} records containing 100% UNIQUE IFSC codes and unique financial details!")


if __name__ == "__main__":
    generate_demo_csv()
