from pathlib import Path

from binance_data_foundation.catchup_transition_representation_audit_v3 import run


if __name__ == "__main__":
    summary = run(Path.cwd())
    print(summary["classification"])
