#!/usr/bin/env bash
set -euo pipefail
exec uv run python scripts/migrate-api-group.py "$@"
