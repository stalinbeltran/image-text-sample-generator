#!/usr/bin/env bash
# One-shot setup on a Debian/Ubuntu box: venv, deps, Chromium, system libs.
# Idempotent -- safe to re-run after pulling new requirements.
#
#   bash scripts/setup-linux.sh
#
# The last step (install-deps) is the only one that needs root, and it is the
# one with no Windows equivalent: headless Chromium links against libnss3,
# libgbm1 and friends, and without them it dies at launch. Skip it with
# NO_SYSTEM_DEPS=1 if you can't sudo -- then ask an admin to run
# `.venv/bin/python -m playwright install --dry-run chromium` and install what
# it lists.
set -euo pipefail

cd "$(dirname "$0")/.."

python3 -m venv .venv
.venv/bin/python -m pip install --upgrade pip
.venv/bin/python -m pip install -r requirements.txt
.venv/bin/python -m playwright install chromium

if [ "${NO_SYSTEM_DEPS:-}" = "1" ]; then
  echo "NO_SYSTEM_DEPS=1 -- skipping the system libraries."
else
  sudo .venv/bin/python -m playwright install-deps chromium
fi

echo
echo "Done. Start it with:"
echo "  .venv/bin/python -m app.serve --reload --port 8001"
