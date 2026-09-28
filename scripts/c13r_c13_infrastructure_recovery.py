#!/usr/bin/env python3
import argparse
from pathlib import Path

from binance_data_foundation.c13_warning_economics import write_json
from binance_data_foundation.c13r_infrastructure_recovery import OUTPUT_REL, preflight, run_once

parser = argparse.ArgumentParser()
parser.add_argument("--repo", default=".")
parser.add_argument("--preflight", action="store_true")
parser.add_argument("--authorization")
args = parser.parse_args()
repo = Path(args.repo).resolve()
if args.preflight:
    value = preflight(repo)
    write_json(repo / OUTPUT_REL / "readiness_freeze.json", value)
    print("C13R READY")
else:
    result = run_once(repo, args.authorization or "")
    print(f"C13R {result['status']}")

