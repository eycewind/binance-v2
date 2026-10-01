#!/usr/bin/env python3
from pathlib import Path
from binance_data_foundation.c31_v4_transition_prediction import run
if __name__ == "__main__": print(run(Path.cwd())["classification"])
