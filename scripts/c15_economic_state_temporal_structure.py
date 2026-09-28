from pathlib import Path
from binance_data_foundation.c15_economic_state_temporal_structure import run

if __name__ == "__main__":
    run(Path(__file__).resolve().parents[1])
