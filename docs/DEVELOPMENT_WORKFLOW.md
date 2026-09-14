# Development Workflow

This repository uses short-lived development branches and pull requests into `main`.

## Branches

- Start future development from current `origin/main` after the preceding accepted work is merged.
- Use one branch per development contract or correction, for example `feature/c2-experiment-foundation` or `fix/c1-resource-budget`.
- Do not push directly to `main`, force-push shared review branches, or delete protected branches.

## Local Checks

Before committing Python or test changes:

```text
conda run -n binance-v2-research python -c 'import sys, platform; print(sys.executable); print(platform.python_version())'
conda run -n binance-v2-research env PYTHONPATH=src pytest -q
git diff --check origin/main...HEAD
```

For package changes, also verify a built wheel imports outside the checkout:

```text
conda run -n binance-v2-research python -m pip wheel --no-deps --no-build-isolation . -w /tmp/binance-v2-wheelcheck
tmp=/tmp/binance-v2-importcheck
rm -rf "$tmp"
conda run -n binance-v2-research python -m venv "$tmp/venv"
"$tmp/venv/bin/python" -m pip install --no-index --find-links /tmp/binance-v2-wheelcheck binance-data-foundation
cd /tmp
"$tmp/venv/bin/python" -c 'import binance_data_foundation; print(binance_data_foundation.__file__)'
```

## Commits And PRs

- Keep accepted baseline work separate from CI/workflow changes where history permits.
- Stage only task-related source, tests, contracts, deliveries, environment/build files, docs and small evidence manifests.
- Exclude credentials, conda environments, raw caches, normalized datasets, generated feature CSVs and review archives.
- PR descriptions should state the problem, summarize changes, include local and CI evidence, name relevant contracts/deliveries, and call out limitations.
- Passing CI is required for review, but it does not replace research-methodology review.

## Review And Merge

Humans manage reviews and merges. Do not merge pull requests automatically. C2 starts only after the baseline/CI PR has been reviewed and merged.
