# skill-ask-slac-ai-tools

SLAC AI tools assistant: SQLite + FTS5 catalog of ~53 AI tools, 5 data classifications, and 12 policy resources, with answers to questions like "Can I use Claude at SLAC?", "Which tools are approved for Moderate-Risk data?", and "Is Cursor allowed?". Centrally deployed for LCLS users via the [deploy-opencode](https://github.com/carbonscott/deploy-opencode) meta-deploy script.

## Layout

```
claude/skills/ask-slac-ai-tools/
  SKILL.md        # skill instructions
  env.sh          # sources env.local; exports SLAC_AI_TOOLS_DB
  env.local       # SLAC-site config: points SLAC_AI_TOOLS_DB at the deployed DB
  setup.sh        # builds build/ai-tooling.db from data/*.json (standalone use)
  schemas/        # JSON schemas validated by setup.sh
  scripts/        # build_db.py, export_from_db.py (PEP 723 uv scripts)
  data/           # curated JSON source: tools, classifications, policies
opencode/skills/ask-slac-ai-tools/
  (identical mirror of claude/skills/ask-slac-ai-tools/)
README.md         # this file
```

The two top-level directories mirror the same content for Claude Code (`~/.claude/skills/ask-slac-ai-tools/`) and OpenCode (`$OPENCODE_CONFIG_DIR/skills/ask-slac-ai-tools/`) runtimes respectively.

## Prerequisites

- [`uv`](https://docs.astral.sh/uv/) on PATH (used by `setup.sh` and the build scripts).
- For SLAC deploy: nothing extra — the DB at `/sdf/group/lcls/ds/dm/apps/dev/data/ask-slac-ai-tools/ai-tooling.db` is built out-of-band and `env.local` already points at it.

## Install

At SLAC LCLS this skill is centrally deployed — set `OPENCODE_CONFIG_DIR=/sdf/group/lcls/ds/dm/apps/dev/opencode` and it loads automatically; no per-user git clone needed.

For standalone use, the `env.local` shipped in this repo points at the SLAC-deployed DB; override it for local use:

**Claude Code:**
```bash
git clone https://github.com/carbonscott/skill-ask-slac-ai-tools.git /tmp/skill-ask-slac-ai-tools
cp -r /tmp/skill-ask-slac-ai-tools/claude/skills/ask-slac-ai-tools ~/.claude/skills/ask-slac-ai-tools
cd ~/.claude/skills/ask-slac-ai-tools
rm -f env.local
./setup.sh
```

**OpenCode:**
```bash
git clone https://github.com/carbonscott/skill-ask-slac-ai-tools.git /tmp/skill-ask-slac-ai-tools
cp -r /tmp/skill-ask-slac-ai-tools/opencode/skills/ask-slac-ai-tools "$OPENCODE_CONFIG_DIR/skills/ask-slac-ai-tools"
cd "$OPENCODE_CONFIG_DIR/skills/ask-slac-ai-tools"
rm -f env.local
./setup.sh
```

`setup.sh` validates `data/*.json` against `schemas/`, builds `build/ai-tooling.db` with FTS5, and writes `env.local` pointing at it.

## What it covers

- Which AI tools are approved at SLAC / Stanford (Claude, GitHub Copilot, Cursor, Microsoft 365 Copilot, Stanford AI Playground, Anthropic API gateway, ...).
- Which data classifications (Low-Risk, Moderate-Risk, High-Risk non-PHI, High-Risk PHI, CUI) each tool may handle.
- Which tools are **not** approved and why.
- Pointers to the underlying SLAC/Stanford policy resources.

## Meta-deploy

Deploys via `carbonscott/deploy-opencode`'s `deploy.sh` reading `skills.manifest.json` — rsyncs `opencode/skills/ask-slac-ai-tools/` into `/sdf/group/lcls/ds/dm/apps/dev/opencode/skills/ask-slac-ai-tools/` with ps-data group + g+rX permissions. Manifest entry has `cron: null` and `central_data: null` — the DB is currently built/refreshed out-of-band.

## License

Apache-2.0
