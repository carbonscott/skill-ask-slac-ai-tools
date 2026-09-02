#!/usr/bin/env -S uv run --quiet --script
# /// script
# requires-python = ">=3.10"
# dependencies = ["jsonschema"]
# ///
"""Validate data/*.json and build build/ai-tooling.db with FTS5 search.

Re-runnable: drops and recreates all tables on each run.
Run with `uv run scripts/build_db.py` (or directly — the shebang invokes uv).
"""

from __future__ import annotations

import json
import sqlite3
import sys
from pathlib import Path

try:
    from jsonschema import Draft202012Validator
except ImportError:
    sys.exit(
        "Missing dependency: jsonschema.\n"
        "Install with:  pip install --user jsonschema"
    )

HERE = Path(__file__).resolve().parent
SKILL_DIR = HERE.parent
DATA_DIR = SKILL_DIR / "data"
SCHEMA_DIR = SKILL_DIR / "schemas"
BUILD_DIR = SKILL_DIR / "build"
DB_PATH = BUILD_DIR / "ai-tooling.db"

SCHEMA_SQL = """
DROP TRIGGER IF EXISTS tools_ai;
DROP TRIGGER IF EXISTS tools_au;
DROP TRIGGER IF EXISTS tools_ad;
DROP TABLE IF EXISTS tools_fts;
DROP TABLE IF EXISTS tool_links;
DROP TABLE IF EXISTS tool_classifications;
DROP TABLE IF EXISTS tools;
DROP TABLE IF EXISTS data_classifications;
DROP TABLE IF EXISTS categories;
DROP TABLE IF EXISTS policy_resources;

CREATE TABLE categories (
    id      INTEGER PRIMARY KEY,
    name    TEXT NOT NULL UNIQUE,
    section TEXT NOT NULL
);

CREATE TABLE data_classifications (
    id      INTEGER PRIMARY KEY,
    label   TEXT NOT NULL UNIQUE,
    meaning TEXT
);

CREATE TABLE tools (
    id                    INTEGER PRIMARY KEY,
    name                  TEXT NOT NULL,
    category_id           INTEGER REFERENCES categories(id),
    provider              TEXT,
    description           TEXT,
    approved_for_text     TEXT,
    not_approved_for_text TEXT,
    reason_not_approved   TEXT,
    notes                 TEXT,
    source_label          TEXT,
    source_url            TEXT,
    UNIQUE (name, category_id)
);

CREATE TABLE tool_classifications (
    tool_id           INTEGER NOT NULL REFERENCES tools(id) ON DELETE CASCADE,
    classification_id INTEGER NOT NULL REFERENCES data_classifications(id),
    PRIMARY KEY (tool_id, classification_id)
);

CREATE TABLE tool_links (
    id      INTEGER PRIMARY KEY,
    tool_id INTEGER NOT NULL REFERENCES tools(id) ON DELETE CASCADE,
    label   TEXT,
    url     TEXT,
    kind    TEXT
);

CREATE TABLE policy_resources (
    id   INTEGER PRIMARY KEY,
    name TEXT NOT NULL,
    url  TEXT
);

CREATE VIRTUAL TABLE tools_fts USING fts5(
    name, description, approved_for_text, not_approved_for_text,
    reason_not_approved, notes, provider,
    content='tools', content_rowid='id', tokenize='porter unicode61'
);

CREATE TRIGGER tools_ai AFTER INSERT ON tools BEGIN
    INSERT INTO tools_fts(rowid, name, description, approved_for_text,
                          not_approved_for_text, reason_not_approved, notes, provider)
    VALUES (new.id, new.name, new.description, new.approved_for_text,
            new.not_approved_for_text, new.reason_not_approved, new.notes, new.provider);
END;

CREATE TRIGGER tools_ad AFTER DELETE ON tools BEGIN
    INSERT INTO tools_fts(tools_fts, rowid, name, description, approved_for_text,
                          not_approved_for_text, reason_not_approved, notes, provider)
    VALUES ('delete', old.id, old.name, old.description, old.approved_for_text,
            old.not_approved_for_text, old.reason_not_approved, old.notes, old.provider);
END;

CREATE TRIGGER tools_au AFTER UPDATE ON tools BEGIN
    INSERT INTO tools_fts(tools_fts, rowid, name, description, approved_for_text,
                          not_approved_for_text, reason_not_approved, notes, provider)
    VALUES ('delete', old.id, old.name, old.description, old.approved_for_text,
            old.not_approved_for_text, old.reason_not_approved, old.notes, old.provider);
    INSERT INTO tools_fts(rowid, name, description, approved_for_text,
                          not_approved_for_text, reason_not_approved, notes, provider)
    VALUES (new.id, new.name, new.description, new.approved_for_text,
            new.not_approved_for_text, new.reason_not_approved, new.notes, new.provider);
END;
"""


def load_json(path: Path):
    with path.open(encoding="utf-8") as f:
        return json.load(f)


def validate(data, schema_path: Path, label: str) -> None:
    schema = load_json(schema_path)
    validator = Draft202012Validator(schema)
    errors = sorted(validator.iter_errors(data), key=lambda e: list(e.absolute_path))
    if errors:
        print(f"Schema validation failed for {label}:", file=sys.stderr)
        for err in errors:
            loc = "/".join(str(p) for p in err.absolute_path) or "<root>"
            print(f"  {loc}: {err.message}", file=sys.stderr)
        sys.exit(1)


def cross_check(tools: list[dict], classifications: list[dict]) -> None:
    valid_labels = {c["label"] for c in classifications}
    bad: list[tuple[str, str]] = []
    for tool in tools:
        for cls in tool.get("approved_classifications", []):
            if cls not in valid_labels:
                bad.append((tool["name"], cls))
    if bad:
        print("Cross-file validation failed:", file=sys.stderr)
        for name, cls in bad:
            print(f"  tool '{name}': unknown classification '{cls}'", file=sys.stderr)
        sys.exit(1)


def build(conn: sqlite3.Connection, tools: list[dict],
          classifications: list[dict], policies: list[dict]) -> None:
    conn.executescript(SCHEMA_SQL)
    cur = conn.cursor()

    classification_id: dict[str, int] = {}
    for entry in classifications:
        cur.execute(
            "INSERT INTO data_classifications(label, meaning) VALUES (?, ?)",
            (entry["label"], entry.get("meaning", "")),
        )
        classification_id[entry["label"]] = cur.lastrowid

    for entry in policies:
        cur.execute(
            "INSERT INTO policy_resources(name, url) VALUES (?, ?)",
            (entry["name"], entry.get("url", "")),
        )

    category_id: dict[tuple[str, str], int] = {}

    def get_or_create_category(name: str, section: str) -> int:
        key = (name, section)
        if key in category_id:
            return category_id[key]
        cur.execute(
            "INSERT INTO categories(name, section) VALUES (?, ?)", (name, section)
        )
        category_id[key] = cur.lastrowid
        return category_id[key]

    for tool in tools:
        cat_id = get_or_create_category(tool["category"], tool["section"])
        source = tool.get("source") or {}
        cur.execute(
            """
            INSERT INTO tools(
                name, category_id, provider, description,
                approved_for_text, not_approved_for_text,
                reason_not_approved, notes, source_label, source_url
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                tool["name"], cat_id,
                tool.get("provider"),
                tool.get("description"),
                tool.get("approved_for_text"),
                tool.get("not_approved_for_text"),
                tool.get("reason_not_approved"),
                tool.get("notes"),
                source.get("label") or None,
                source.get("url") or None,
            ),
        )
        tool_id = cur.lastrowid

        for link in tool.get("access_links", []):
            cur.execute(
                "INSERT INTO tool_links(tool_id, label, url, kind) "
                "VALUES (?, ?, ?, 'access')",
                (tool_id, link["label"], link["url"]),
            )
        if source:
            cur.execute(
                "INSERT INTO tool_links(tool_id, label, url, kind) "
                "VALUES (?, ?, ?, 'source')",
                (tool_id, source.get("label", ""), source.get("url", "")),
            )

        for cls in tool.get("approved_classifications", []):
            cur.execute(
                "INSERT OR IGNORE INTO tool_classifications(tool_id, classification_id) "
                "VALUES (?, ?)",
                (tool_id, classification_id[cls]),
            )


def verify(conn: sqlite3.Connection) -> None:
    cur = conn.cursor()
    print("--- verification ---")
    for table in (
        "categories", "data_classifications", "tools",
        "tool_classifications", "tool_links", "policy_resources",
    ):
        cur.execute(f"SELECT COUNT(*) FROM {table}")
        print(f"  {table:24s} {cur.fetchone()[0]}")

    cur.execute(
        "SELECT COUNT(*) FROM tools WHERE id IN "
        "(SELECT rowid FROM tools_fts WHERE tools_fts MATCH 'bedrock')"
    )
    print(f"\n  FTS5 'bedrock' hits: {cur.fetchone()[0]}")

    cur.execute(
        "SELECT COUNT(*) FROM tools WHERE id IN "
        "(SELECT rowid FROM tools_fts WHERE tools_fts MATCH 'phi')"
    )
    print(f"  FTS5 'phi' hits:     {cur.fetchone()[0]}")


def main() -> None:
    tools = load_json(DATA_DIR / "tools.json")
    classifications = load_json(DATA_DIR / "classifications.json")
    policies = load_json(DATA_DIR / "policies.json")

    validate(classifications, SCHEMA_DIR / "classifications.schema.json", "classifications.json")
    validate(policies, SCHEMA_DIR / "policies.schema.json", "policies.json")
    validate(tools, SCHEMA_DIR / "tools.schema.json", "tools.json")
    cross_check(tools, classifications)

    BUILD_DIR.mkdir(parents=True, exist_ok=True)
    if DB_PATH.exists():
        DB_PATH.unlink()

    conn = sqlite3.connect(DB_PATH)
    try:
        conn.execute("PRAGMA foreign_keys = ON")
        with conn:
            build(conn, tools, classifications, policies)
        verify(conn)
    finally:
        conn.close()
    print(f"\nWrote {DB_PATH}")


if __name__ == "__main__":
    main()
