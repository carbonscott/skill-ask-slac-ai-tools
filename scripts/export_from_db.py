#!/usr/bin/env python3
"""One-shot exporter: dump an existing ai-tooling .db into data/*.json.

Reads from a path given as argv[1] (defaults to the original .db location)
and writes tools.json, classifications.json, policies.json into ../data/
relative to this script. Stdlib only.
"""

from __future__ import annotations

import json
import sqlite3
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
SKILL_DIR = HERE.parent
DATA_DIR = SKILL_DIR / "data"

DEFAULT_SRC = Path(
    "/Users/cwang31/Library/CloudStorage/OneDrive-SLACNationalAcceleratorLaboratory"
    "/obsidian/externals/ai-tooling-for-slac.db"
)


def fetch_classifications(conn: sqlite3.Connection) -> list[dict]:
    rows = conn.execute(
        "SELECT label, meaning FROM data_classifications ORDER BY id"
    ).fetchall()
    return [{"label": label, "meaning": meaning or ""} for label, meaning in rows]


def fetch_policies(conn: sqlite3.Connection) -> list[dict]:
    rows = conn.execute(
        "SELECT name, url FROM policy_resources ORDER BY id"
    ).fetchall()
    return [{"name": name, "url": url or ""} for name, url in rows]


def fetch_tools(conn: sqlite3.Connection) -> list[dict]:
    tool_rows = conn.execute(
        """
        SELECT t.id, t.name, c.section, c.name AS category, t.provider,
               t.description, t.approved_for_text, t.not_approved_for_text,
               t.reason_not_approved, t.notes, t.source_label, t.source_url
        FROM tools t
        JOIN categories c ON c.id = t.category_id
        ORDER BY c.section, c.name, t.name
        """
    ).fetchall()

    tools: list[dict] = []
    for (tid, name, section, category, provider, description,
         approved_for_text, not_approved_for_text, reason_not_approved,
         notes, source_label, source_url) in tool_rows:

        classifications = [
            row[0]
            for row in conn.execute(
                """
                SELECT dc.label FROM tool_classifications tc
                JOIN data_classifications dc ON dc.id = tc.classification_id
                WHERE tc.tool_id = ?
                ORDER BY dc.id
                """,
                (tid,),
            )
        ]

        access_links = [
            {"label": label, "url": url}
            for label, url in conn.execute(
                "SELECT label, url FROM tool_links "
                "WHERE tool_id = ? AND kind = 'access' ORDER BY id",
                (tid,),
            )
        ]

        source = None
        if source_url or source_label:
            source = {"label": source_label or "", "url": source_url or ""}

        tools.append({
            "name": name,
            "section": section,
            "category": category,
            "provider": provider,
            "description": description,
            "approved_for_text": approved_for_text,
            "not_approved_for_text": not_approved_for_text,
            "reason_not_approved": reason_not_approved,
            "notes": notes,
            "approved_classifications": classifications,
            "access_links": access_links,
            "source": source,
        })
    return tools


def write_json(path: Path, data) -> None:
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"wrote {path} ({len(data)} records)")


def main() -> None:
    src = Path(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_SRC
    if not src.exists():
        sys.exit(f"source db not found: {src}")
    DATA_DIR.mkdir(parents=True, exist_ok=True)

    conn = sqlite3.connect(src)
    try:
        write_json(DATA_DIR / "classifications.json", fetch_classifications(conn))
        write_json(DATA_DIR / "policies.json", fetch_policies(conn))
        write_json(DATA_DIR / "tools.json", fetch_tools(conn))
    finally:
        conn.close()


if __name__ == "__main__":
    main()
