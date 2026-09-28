#!/usr/bin/env python3
import argparse
from pathlib import Path
from binance_data_foundation.c13_warning_economics import AUTHORIZATION, preflight, run_once, write_json

p=argparse.ArgumentParser();p.add_argument("--repo",default=".");p.add_argument("--preflight",action="store_true");p.add_argument("--authorization")
a=p.parse_args();repo=Path(a.repo).resolve()
if a.preflight:
    value=preflight(repo);write_json(repo/"artifacts/c13_post_t2_warning_economics/readiness_freeze.json",value);print("C13 READY")
else:
    run_once(repo,a.authorization or "");print("C13 PASS")
