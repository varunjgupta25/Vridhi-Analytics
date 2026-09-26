"""Multi-Bank Dedicated Server Orchestrator for Windows.

Launches all 10 isolated bank server nodes (SBI, MAHB, CBIN, BOB, PNB, UBI, CANARA, MGB, ICICI, HDFC)
and the Central Gateway on a single laptop with a single command.
"""

from __future__ import annotations

import os
import sys
import time
import socket
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

NODES = [
    {"name": "Central Gateway Router", "port": 8000, "bank_code": "ALL"},
    {"name": "State Bank of India Node", "port": 8001, "bank_code": "SBIN"},
    {"name": "Bank of Maharashtra Node", "port": 8002, "bank_code": "MAHB"},
    {"name": "Central Bank of India Node", "port": 8003, "bank_code": "CBIN"},
    {"name": "Bank of Baroda Node", "port": 8004, "bank_code": "BARB"},
    {"name": "Punjab National Bank Node", "port": 8005, "bank_code": "PUNB"},
    {"name": "Union Bank of India Node", "port": 8006, "bank_code": "UBIN"},
    {"name": "Canara Bank Node", "port": 8007, "bank_code": "CNRB"},
    {"name": "Maharashtra Gramin Bank Node", "port": 8008, "bank_code": "MAHG"},
    {"name": "ICICI Rural Bank Node", "port": 8009, "bank_code": "ICIC"},
    {"name": "HDFC Rural Bank Node", "port": 8010, "bank_code": "HDFC"},
]


def get_local_ip() -> str:
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        # Connect to a dummy public IP to resolve local interface IP
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return "127.0.0.1"


def launch_all_nodes():
    local_ip = get_local_ip()

    print("=" * 65)
    print(" [LAUNCH] VRIDHI ANALYTICS - MULTI-BANK DEDICATED SERVER NETWORK")
    print("=" * 65)
    print(f"  Local Network IP Address of this laptop: {local_ip}")
    print("=" * 65)

    processes = []
    env = os.environ.copy()
    env["PYTHONPATH"] = str(ROOT / "src")

    for node in NODES:
        cmd = [
            sys.executable,
            "-m",
            "uvicorn",
            "vridhi_sim.backend:app",
            "--host",
            "0.0.0.0",
            "--port",
            str(node["port"]),
            "--log-level",
            "warning",
        ]
        p = subprocess.Popen(cmd, env=env, cwd=str(ROOT))
        processes.append((node, p))
        print(f"  [OK] Started {node['name']} -> http://{local_ip}:{node['port']}/")
        time.sleep(0.3)  # Slightly faster start

    print("=" * 65)
    print(f"  Central Gateway UI: http://{local_ip}:8000/app/")
    print(f"  SBI Isolated Node:  http://{local_ip}:8001/v1/bank/sbi/borrowers")
    print(f"  MAHB Isolated Node: http://{local_ip}:8002/v1/bank/mahb/borrowers")
    print(f"  CBIN Isolated Node: http://{local_ip}:8003/v1/bank/cbin/borrowers")
    print(f"  7 More Bank Servers online on ports 8004 to 8010.")
    print("=" * 65)
    print(" Press Ctrl+C anytime to stop all bank servers.\n")

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\n [STOP] Stopping all bank server nodes...")
        for node, p in processes:
            p.terminate()
        print(" All bank server nodes stopped cleanly.")


if __name__ == "__main__":
    launch_all_nodes()
