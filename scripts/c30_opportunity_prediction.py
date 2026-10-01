#!/usr/bin/env python3
from pathlib import Path
from binance_data_foundation.c30_opportunity_prediction import run

if __name__ == "__main__":
    result = run(Path.cwd())
    print(result["classification"])
