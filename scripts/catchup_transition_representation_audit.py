from pathlib import Path

from binance_data_foundation.catchup_transition_representation_audit import run


if __name__ == "__main__":
    result = run(Path.cwd())
    print(result["classification"])
