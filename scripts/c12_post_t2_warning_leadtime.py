#!/usr/bin/env python3
from pathlib import Path
from binance_data_foundation.c12_post_t2_warning import run

if __name__ == "__main__":
    result=run(Path(__file__).resolve().parents[1])
    print(result["adequacy"]["classification"])
