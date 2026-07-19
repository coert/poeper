#!/usr/bin/env bash

set -Eeuo pipefail

project_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
cd "$project_dir"

if [[ -z "${POEPER_ADMIN_TOKEN:-}" ]]; then
    echo "Error: POEPER_ADMIN_TOKEN must be set before starting production." >&2
    exit 1
fi

if ! command -v uv >/dev/null 2>&1; then
    echo "Error: uv is required to start POEPER." >&2
    exit 1
fi

exec uv run --frozen python production.py
