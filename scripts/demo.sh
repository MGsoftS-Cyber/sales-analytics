#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
if [ ! -d data/raw ]; then python3 -m generator.generate --rows 10000; fi
python3 -m pipeline.run --engine reference
python3 -m app.local
