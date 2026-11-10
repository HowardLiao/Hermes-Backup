#!/bin/bash
# ==============================================================================
# Hermes-Backup: Automated Daily Differential Backup Runner
# Author: Howard Liao, Ph.D.
# ==============================================================================
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PYTHON_EXEC="/usr/bin/python3"
[ -x "$HOME/.hermes/hermes-agent/venv/bin/python" ] && PYTHON_EXEC="$HOME/.hermes/hermes-agent/venv/bin/python"

"$PYTHON_EXEC" "$SCRIPT_DIR/differential_backup.py"
