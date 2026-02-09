#!/usr/bin/env bash
# Wrapper script that loads repo config and runs fizban
set -euo pipefail

ENV_FILE="${HOME}/.config/fizban/env"
if [ -f "$ENV_FILE" ]; then
    # shellcheck disable=SC1090
    source "$ENV_FILE"
    export FIZBAN_REPOS
fi

exec "${HOME}/fizban/.venv/bin/fizban" "$@"
