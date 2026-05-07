#!/bin/bash
# setup.sh — One-time local setup for ask-slac-ai-tools.
#
# Validates data/*.json against schemas/, builds build/ai-tooling.db with FTS5,
# and writes env.local so the skill is ready to use.
#
# Idempotent: re-running always rebuilds the database from scratch.
# Requires: uv (https://docs.astral.sh/uv/).
set -euo pipefail

SKILL_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

if ! command -v uv >/dev/null 2>&1; then
    echo "Error: 'uv' is not on PATH. Install it first: https://docs.astral.sh/uv/" >&2
    exit 1
fi

echo "Building ai-tooling.db from data/*.json ..."
uv run --quiet --script "$SKILL_DIR/scripts/build_db.py"

cat > "$SKILL_DIR/env.local" <<EOF
export SLAC_AI_TOOLS_DB="$SKILL_DIR/build/ai-tooling.db"
EOF

echo ""
echo "Done. Skill is ready to use."
echo "env.local created at: $SKILL_DIR/env.local"
