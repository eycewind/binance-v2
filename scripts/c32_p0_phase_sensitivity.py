from pathlib import Path

from binance_data_foundation.c32_p0_phase_sensitivity import run


if __name__ == "__main__":
    result = run(Path.cwd())
    print(result["classification"])
    print(result["failure_reason"])
