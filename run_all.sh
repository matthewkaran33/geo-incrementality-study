#!/bin/bash
# Reproduce the full study end to end.
set -e
cd "$(dirname "$0")"
python3 analysis/simulate.py
python3 analysis/design.py
python3 analysis/analyze.py
python3 analysis/plots.py
echo "done -- see charts/ and docs/case_study.md"
