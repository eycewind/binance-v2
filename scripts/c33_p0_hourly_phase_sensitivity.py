from pathlib import Path

from binance_data_foundation.c33_p0_hourly_phase_sensitivity import run


if __name__ == "__main__":
    result = run(Path.cwd())
    print(result["classification"])
    print(f"RETIRE_MODEL_FAMILY={result['RETIRE_MODEL_FAMILY']}")
