from pathlib import Path

from binance_data_foundation.catchup_transition_representation_audit_v4 import run


if __name__ == "__main__":
    print(run(Path.cwd())["classification"])
