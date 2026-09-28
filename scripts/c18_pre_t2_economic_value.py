from pathlib import Path
from binance_data_foundation.c18_pre_t2_economic_value import run

if __name__ == "__main__":
    run(Path(__file__).resolve().parents[1])
