from pathlib import Path
from binance_data_foundation.c26_q1_action_semantics import run

if __name__ == "__main__":
    result=run(Path.cwd())
    print(result["decision"])
