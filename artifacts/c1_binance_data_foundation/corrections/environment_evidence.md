# C1 Corrections Environment Evidence

Date: 2026-09-14

Verified environment before tests and project Python commands:

```text
CONDA_DEFAULT_ENV=binance-v2-research
python=3.11.16 (main, Aug 27 2026, 14:44:21) [GCC 14.3.0]
executable=/home/ata/miniconda3/envs/binance-v2-research/bin/python
platform=Linux-5.15.0-139-generic-x86_64-with-glibc2.31
```

Direct verification commands rerun on 2026-09-14:

```text
conda run -n binance-v2-research python --version
Python 3.11.16

conda run -n binance-v2-research python -c 'import sys; print(sys.executable)'
/home/ata/miniconda3/envs/binance-v2-research/bin/python
```

Resolved Python packages:

```text
iniconfig @ file:///home/task_176735680440987/croot/iniconfig_1767356866218/work
packaging==26.3
pluggy @ file:///home/task_177697287510845/croot/pluggy_1776972921328/work
Pygments @ file:///home/task_177512698038530/croot/pygments_1775127007107/work
pytest @ file:///home/task_177765442676784/croot/pytest_1777654749919/work
```
