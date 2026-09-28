from pathlib import Path
from binance_data_foundation.c14_post_t2_economic_state import run

if __name__ == "__main__":
    run(Path(__file__).resolve().parents[1])
