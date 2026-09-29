from pathlib import Path

from binance_data_foundation.c28_strategy_economic_review import run


if __name__ == "__main__":
    run(Path(__file__).resolve().parents[1])
