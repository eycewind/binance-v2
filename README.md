# binance-v2

See [docs/DEVELOPMENT_WORKFLOW.md](docs/DEVELOPMENT_WORKFLOW.md) for the branch, CI and pull-request workflow.

## C4 2024 portable freeze rebuild

The supported offline workflow is an editable install from this repository:

```bash
PIP_NO_INDEX=1 python -m pip install --no-build-isolation --no-deps -e .
python -m binance_data_foundation.c4_modeling_cli --portable-rebuild \
  --artifact-dir /tmp/c4-rebuild
```

If the conda environment is read-only, create a temporary virtual environment
that inherits its pinned packages, install the repository there, and use the
same module invocation:

```bash
python -m venv --system-site-packages /tmp/c4-editable-env
PIP_NO_INDEX=1 /tmp/c4-editable-env/bin/python -m pip install \
  --no-build-isolation --no-deps -e .
CONDA_DEFAULT_ENV=binance-v2-research \
  /tmp/c4-editable-env/bin/python -m binance_data_foundation.c4_modeling_cli \
  --portable-rebuild --artifact-dir /tmp/c4-rebuild
```

`PYTHONPATH` must remain unset. Portable rebuild regenerates the ignored T1/T2
audit tables and bootstrap multiplicities from the accepted upstream allowlist,
requires their accepted hashes to match, and only then starts 2024 modeling.
The locked evaluator is the separate prediction-only module
`binance_data_foundation.c4_locked_eval_cli`; it requires a matching external
`c4_2024_freeze.sha256` lock and exposes no fitting or selection operation.
Validate the complete seal without opening predictive input with:

```bash
python -m binance_data_foundation.c4_locked_eval_cli --repo . --readiness
```

The later authorized one-shot operation is `--evaluate-locked-2025`. It always
evaluates both targets and all four frozen models, writes the fixed output set,
and accepts no target, model, metric, calibration, or interpretation choices.
