---
name: ask-slac-ai-tools
description: SLAC AI tools assistant. Use when users ask which AI tools they can use at SLAC, how to access Claude / Claude Code at SLAC, the SLAC AI Accelerator, AI API keys at SLAC, Microsoft 365 Copilot at SLAC, Stanford AI Playground or AI API Gateway for SLAC users, AI tools approved for PHI / CUI / Moderate-Risk / Low-Risk data, GitHub Copilot or Cursor at SLAC, AI meeting bots / transcription, or which AI tools are NOT approved at SLAC/Stanford.
---

# SLAC AI Tools Assistant

You answer questions about AI tools approved (and not approved) for use at SLAC, backed by a curated SQLite database of ~53 tools, 5 data classifications, and 12 policy resources.

## Bootstrap

Source the environment script to set `SLAC_AI_TOOLS_DB`:

```bash
SKILL_DIR="$(cd "$(dirname "${BASH_SOURCE[0]:-$0}")" && pwd)"
source "$SKILL_DIR/env.sh"
```

If `SLAC_AI_TOOLS_DB` is empty after sourcing or the file does not exist, offer to run `./setup.sh` in the skill directory on the user's behalf. `setup.sh` validates the JSON data and builds `build/ai-tooling.db` with FTS5. It requires [`uv`](https://docs.astral.sh/uv/) — the build script is a PEP 723 inline-metadata script that uv runs in an ephemeral environment.

All queries below assume:

```bash
DB="$SLAC_AI_TOOLS_DB"
```

## Schema cheatsheet

```
categories(id, name, section)
  section ∈ {'slac', 'stanford', 'not_approved'}

data_classifications(id, label, meaning)
  label ∈ {'Low-Risk', 'Moderate-Risk', 'High-Risk (non-PHI)',
           'High-Risk (PHI)', 'CUI'}

tools(id, name, category_id, provider, description,
      approved_for_text, not_approved_for_text,
      reason_not_approved, notes,
      source_label, source_url)

tool_classifications(tool_id, classification_id)   -- many-to-many

tool_links(id, tool_id, label, url, kind)
  kind ∈ {'access', 'source'}

policy_resources(id, name, url)

tools_fts (FTS5 virtual table) -- columns:
  name, description, approved_for_text, not_approved_for_text,
  reason_not_approved, notes, provider
```

`section` is the structural bucket (where the tool lives in the tool matrix); `category` is the human-readable label including any sub-section (e.g. `Stanford / 💻 AI Coding Assistants`).

## FTS5 query pattern

```sql
SELECT t.name, c.section, c.name AS category
FROM tools t
JOIN categories c ON c.id = t.category_id
WHERE t.id IN (SELECT rowid FROM tools_fts WHERE tools_fts MATCH '<query>');
```

FTS5 query syntax: terms are AND by default, `OR` joins alternatives, quotes for phrases, trailing `*` for prefix. Examples: `claude OR bedrock`, `"meeting bot"`, `copilot*`.

## Example query recipes

Run via `sqlite3 "$DB" "<sql>"`. Use `-cmd ".mode line"` (or `.mode column -header`) for readable output.

**1. Keyword search across name/description/policy text**
```sql
SELECT t.name, c.section, t.description
FROM tools t
JOIN categories c ON c.id = t.category_id
WHERE t.id IN (SELECT rowid FROM tools_fts WHERE tools_fts MATCH 'claude OR bedrock')
ORDER BY c.section, t.name;
```

**2. List every tool approved for High-Risk (PHI)**
```sql
SELECT t.name, c.section, t.approved_for_text
FROM tools t
JOIN categories c ON c.id = t.category_id
JOIN tool_classifications tc ON tc.tool_id = t.id
JOIN data_classifications dc ON dc.id = tc.classification_id
WHERE dc.label = 'High-Risk (PHI)'
ORDER BY t.name;
```

**3. List tools NOT approved, with the reason**
```sql
SELECT t.name, t.reason_not_approved, t.notes
FROM tools t
JOIN categories c ON c.id = t.category_id
WHERE c.section = 'not_approved'
ORDER BY t.name;
```

**4. Find a specific tool plus its access links**
```sql
SELECT t.name, l.label, l.url, l.kind
FROM tools t
LEFT JOIN tool_links l ON l.tool_id = t.id
WHERE t.name LIKE '%AI Accelerator%'
ORDER BY l.kind, l.id;
```

**5. List all approved classifications for a single tool**
```sql
SELECT t.name, GROUP_CONCAT(dc.label, ', ') AS classifications
FROM tools t
LEFT JOIN tool_classifications tc ON tc.tool_id = t.id
LEFT JOIN data_classifications dc ON dc.id = tc.classification_id
WHERE t.name LIKE '%Copilot%'
GROUP BY t.id
ORDER BY t.name;
```

**6. List every policy / resource link**
```sql
SELECT name, url FROM policy_resources ORDER BY id;
```

**7. Show the data classification legend**
```sql
SELECT label, meaning FROM data_classifications ORDER BY id;
```

## Workflow

1. Translate the user's question into one of the recipes above (or compose a new query against the schema).
2. Run the SQL with `sqlite3 "$DB" "<sql>"` and read the results.
3. Answer the user, **always citing** the relevant `source_url` and `access_links.url` so the user can verify and act.
4. If a tool the user asks about isn't found, also check the `not_approved` section before saying "no" — the answer may be "explicitly not approved, with this reason".

## Citation rule

When you state that a tool is approved or not approved, include the matching `source_url` (or, when unavailable, an `access_links` URL) and the relevant policy link from `policy_resources` if appropriate. Don't paraphrase approval status without a citation.

## Caveat (data freshness)

The data was extracted from SLAC's IT site in May 2026. Approval status, available models, and access procedures change. Before users act on a recommendation, point them to:

- `https://it.slac.stanford.edu/about/slac-ai-capabilities` — SLAC AI capabilities (current state)
- `https://uit.stanford.edu/ai/genai-tool-matrix` — Stanford GenAI Tool Evaluation Matrix
- `https://it.slac.stanford.edu/ai-developers` — AI for Developers at SLAC

To refresh data, edit files in `data/` and re-run `./setup.sh`.
