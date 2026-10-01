from pathlib import Path

from binance_data_foundation.c34_p0_downside_characterization import run


if __name__ == "__main__":
    result = run(Path.cwd())
    print(result["classification"])
    print(f"events={result['total_events']}")
