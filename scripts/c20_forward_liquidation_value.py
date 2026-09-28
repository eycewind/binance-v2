from pathlib import Path
from binance_data_foundation.c20_forward_liquidation_value import run

if __name__ == "__main__":
    run(Path(__file__).resolve().parents[1])
