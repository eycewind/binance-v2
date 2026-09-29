from pathlib import Path
from binance_data_foundation.c22_causal_decision_state import run

if __name__ == "__main__":
    run(Path(__file__).resolve().parents[1])
