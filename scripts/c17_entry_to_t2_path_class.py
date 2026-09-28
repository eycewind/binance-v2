from pathlib import Path
from binance_data_foundation.c17_entry_to_t2_path_class import run

if __name__ == "__main__":
    run(Path(__file__).resolve().parents[1])
