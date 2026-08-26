#!/usr/bin/env python3
"""Deterministically validate a complete Hermes project bench."""

from __future__ import annotations

import argparse
import hashlib
import json
import sqlite3
import sys
from pathlib import Path
from typing import Any

CORE_KEYS = ("agents", "overview", "plan", "progress", "decisions", "execution_log")
REQUIRED_DIRS = ("docs", "artifacts", "_scratch", ".project", ".project/canonical", "tools")
COMPETING_CONTEXT = (".hermes.md", "HERMES.md", "agents.md", "AGENTS.override.md")
PROJECTS_DB = Path("/opt/data/projects.db")
KANBAN_ROOT = Path("/opt/data/kanban/boards")


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for block in iter(lambda: fh.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def load_json(path: Path, errors: list[str]) -> dict[str, Any]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        errors.append(f"invalid JSON: {path}: {exc}")
        return {}
    if not isinstance(data, dict):
        errors.append(f"expected JSON object: {path}")
        return {}
    return data


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("bench", nargs="?", default=".")
    args = parser.parse_args()

    root = Path(args.bench).resolve()
    errors: list[str] = []
    checks: dict[str, Any] = {}
    doc_states: dict[str, Any] = {}

    project_path = root / "project.json"
    sync_path = root / ".project" / "sync-state.json"

    if not root.is_dir():
        errors.append(f"bench is not a directory: {root}")
    if not project_path.is_file():
        errors.append("missing project.json")
    if not sync_path.is_file():
        errors.append("missing .project/sync-state.json")

    project = load_json(project_path, errors) if project_path.is_file() else {}
    sync = load_json(sync_path, errors) if sync_path.is_file() else {}

    slug = project.get("slug")
    expected_workspace = project.get("workspace_path")
    board_slug = project.get("board_slug")
    core = project.get("core_documents") if isinstance(project.get("core_documents"), dict) else {}

    checks["root"] = str(root)
    checks["slug"] = slug
    checks["workspace_matches"] = expected_workspace == str(root)
    if not checks["workspace_matches"]:
        errors.append(f"workspace mismatch: manifest={expected_workspace!r}, actual={str(root)!r}")

    if not isinstance(slug, str) or not slug:
        errors.append("project.json has no valid slug")
    if board_slug != slug:
        errors.append(f"board slug mismatch: {board_slug!r} != {slug!r}")
    if project.get("canonical_writer") != "gbrain-mcp":
        errors.append("canonical_writer must be gbrain-mcp")
    if project.get("worker_root") != str(root):
        errors.append("worker_root must equal the bench path")

    metadata = project.get("metadata") if isinstance(project.get("metadata"), dict) else {}
    required_tools = {
        "validator": "tools/validate_project_bench.py",
        "synchronizer": "tools/gbrain_sync_cli.py",
        "sync_engine": "tools/project_sync.py",
        "test_suite": "tests",
    }
    for field, expected in required_tools.items():
        if metadata.get(field) != expected:
            errors.append(f"metadata {field} must be {expected}")
        target = root / expected
        if field == "test_suite":
            if not target.is_dir():
                errors.append(f"test suite directory missing: {expected}")
        elif not target.is_file():
            errors.append(f"project tool missing: {expected}")

    for rel in REQUIRED_DIRS:
        if not (root / rel).is_dir():
            errors.append(f"missing required directory: {rel}")

    agents = root / "AGENTS.md"
    if not agents.is_file() or agents.is_symlink():
        errors.append("AGENTS.md must be a real local file")
    for name in COMPETING_CONTEXT:
        if (root / name).exists() or (root / name).is_symlink():
            errors.append(f"competing context file exists: {name}")

    escaped_symlinks: list[str] = []
    for path in root.rglob("*"):
        if not path.is_symlink():
            continue
        try:
            path.resolve().relative_to(root)
        except (OSError, ValueError):
            escaped_symlinks.append(str(path.relative_to(root)))
    checks["escaped_symlinks"] = escaped_symlinks
    if escaped_symlinks:
        errors.append("symlinks escape bench: " + ", ".join(escaped_symlinks))

    sync_docs = sync.get("documents") if isinstance(sync.get("documents"), dict) else {}
    if sync.get("schema_version") != 1:
        errors.append("sync-state schema_version must be 1")
    if sync.get("slug") != slug:
        errors.append("sync-state slug does not match project.json")
    if sync.get("source") != project.get("cortex_source"):
        errors.append("sync-state source does not match project.json")

    for key in CORE_KEYS:
        spec = core.get(key) if isinstance(core.get(key), dict) else {}
        state = sync_docs.get(key) if isinstance(sync_docs.get(key), dict) else {}
        local_rel = spec.get("local")
        canonical_slug = spec.get("canonical_slug")
        expected_snapshot = f".project/canonical/{key}.md"
        local_path = root / str(local_rel) if local_rel else root / "__missing__"
        snapshot_path = root / expected_snapshot

        if not local_rel or not local_path.is_file() or local_path.is_symlink():
            errors.append(f"{key}: missing real local working document: {local_rel!r}")
        if not snapshot_path.is_file() or snapshot_path.is_symlink():
            errors.append(f"{key}: missing real canonical snapshot: {expected_snapshot}")

        local_hash = sha256(local_path) if local_path.is_file() else None
        snapshot_hash = sha256(snapshot_path) if snapshot_path.is_file() else None
        baseline_hash = state.get("baseline_sha256")
        canonical_hash = state.get("canonical_content_hash")

        if state.get("local_path") != local_rel:
            errors.append(f"{key}: sync local_path mismatch")
        if state.get("snapshot_path") != expected_snapshot:
            errors.append(f"{key}: sync snapshot_path mismatch")
        if state.get("canonical_slug") != canonical_slug:
            errors.append(f"{key}: sync canonical_slug mismatch")
        if snapshot_hash and baseline_hash != snapshot_hash:
            errors.append(f"{key}: baseline hash does not match snapshot")
        if not isinstance(canonical_hash, str) or len(canonical_hash) != 64:
            errors.append(f"{key}: invalid canonical content hash")

        doc_states[key] = {
            "local_path": local_rel,
            "snapshot_path": expected_snapshot,
            "local_sha256": local_hash,
            "baseline_sha256": snapshot_hash,
            "state": "unchanged" if local_hash and local_hash == snapshot_hash else "local_changed",
            "canonical_slug": canonical_slug,
            "canonical_content_hash": canonical_hash,
        }

    db_row = None
    if PROJECTS_DB.is_file() and slug:
        try:
            con = sqlite3.connect(PROJECTS_DB)
            con.row_factory = sqlite3.Row
            row = con.execute(
                "select id, slug, primary_path, board_slug, archived from projects where slug = ?",
                (slug,),
            ).fetchone()
            db_row = dict(row) if row else None
        except Exception as exc:
            errors.append(f"projects.db check failed: {exc}")
        finally:
            try:
                con.close()
            except Exception:
                pass
    else:
        errors.append("projects.db unavailable or slug missing")

    checks["projects_db"] = db_row
    if not db_row:
        errors.append("projects.db row missing")
    else:
        if db_row.get("archived"):
            errors.append("projects.db project is archived")
        if db_row.get("primary_path") != str(root):
            errors.append("projects.db primary_path mismatch")
        if db_row.get("board_slug") != slug:
            errors.append("projects.db board_slug mismatch")
        if project.get("hermes_project_id") != db_row.get("id"):
            errors.append("Hermes project ID mismatch")

    board_db = KANBAN_ROOT / str(slug) / "kanban.db"
    checks["board_db"] = str(board_db)
    checks["board_exists"] = board_db.is_file()
    if not board_db.is_file():
        errors.append(f"Kanban board database missing: {board_db}")

    result = {
        "status": "pass" if not errors else "fail",
        "bench": str(root),
        "checks": checks,
        "documents": doc_states,
        "errors": errors,
    }
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if not errors else 1


if __name__ == "__main__":
    sys.exit(main())
