import argparse
from pathlib import Path
from binance_data_foundation.c13f_frozen_science_repair import AUTHORIZATION, preflight, run_once

if __name__=="__main__":
    p=argparse.ArgumentParser();p.add_argument("--execute",action="store_true");p.add_argument("--authorization",default="");a=p.parse_args();repo=Path(__file__).resolve().parents[1]
    if a.execute:print(run_once(repo,a.authorization))
    else:print(preflight(repo))
