from pathlib import Path
from binance_data_foundation.c23_incremental_c9_ablation import run

if __name__ == "__main__":
    run(Path(__file__).resolve().parents[1])
