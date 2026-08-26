#!/usr/bin/env python3
"""Validate Hermes project, board, startup-context, and worker alignment."""

from __future__ import annotations

import argparse
import json
import re
import sqlite3
import sys
from pathlib import Path
from typing import Any

NONTERMINAL_STATUSES = ("triage", "todo", "scheduled", "ready", "running", "blocked", "review")
REQUIRED_FORBIDDEN_PATHS = {"/cortex", "/opt/data", "/docker-compose", "/repos"}
REQUIRED_ORCHESTRATOR_ONLY = {
    ".project/canonical",
    ".project/sync-state.json",
    "project.json",
}


class DispatchNotAuthorized(RuntimeError):
    """Raised when the project alignment contract does not authorize dispatch."""


def _load_json(path: Path, errors: list[str], label: str) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        errors.append(f"invalid {label}: {exc}")
        return {}
    if not isinstance(value, dict):
        errors.append(f"invalid {label}: expected JSON object")
        return {}
    return value


def _profile_exposes_gbrain(profile_dir: Path) -> bool:
    config = profile_dir / "config.yaml"
    if config.is_file():
        text = config.read_text(encoding="utf-8", errors="replace")
        block = re.search(r"(?ms)^mcp_servers:\s*\n((?:^[ \t]+.*\n?)*)", text)
        if block and re.search(r"(?m)^\s+gbrain\s*:", block.group(1)):
            return True
    for name in ("mcp_servers.json", "mcp.json"):
        path = profile_dir / name
        if not path.is_file():
            continue
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            continue
        if isinstance(payload, dict) and "gbrain" in payload:
            return True
    return False


def validate_alignment(
    root: Path,
    *,
    projects_db: Path = Path("/opt/data/projects.db"),
    kanban_root: Path = Path("/opt/data/kanban/boards"),
    profiles_root: Path = Path("/opt/data/profiles"),
) -> dict[str, Any]:
    root = root.resolve()
    errors: list[str] = []
    checks: dict[str, Any] = {}

    project_path = root / "project.json"
    if not project_path.is_file():
        errors.append("missing project.json")
        project: dict[str, Any] = {}
    else:
        project = _load_json(project_path, errors, "project.json")

    slug = project.get("slug")
    project_id = project.get("hermes_project_id")
    if project.get("schema_version") != 2:
        errors.append("project.json schema_version must be 2")
    if project.get("workspace_path") != str(root):
        errors.append("project workspace_path mismatch")
    if not isinstance(slug, str) or not slug:
        errors.append("project slug is missing")
    if project.get("board_slug") != slug:
        errors.append("project board_slug must equal slug")

    startup = project.get("startup_context") if isinstance(project.get("startup_context"), dict) else {}
    context_file = startup.get("file")
    context_path = root / str(context_file) if context_file else root / "__missing__"
    if context_file != "AGENTS.md":
        errors.append("startup context file must be AGENTS.md")
    if not context_path.is_file() or context_path.is_symlink():
        errors.append("startup AGENTS.md must be a real local file")
    if startup.get("discovery") != "outside-git-cwd-only":
        errors.append("startup discovery must be outside-git-cwd-only")
    max_characters = startup.get("max_characters")
    if max_characters != 20000:
        errors.append("startup max_characters must be 20000")
    elif context_path.is_file() and len(context_path.read_text(encoding="utf-8")) > max_characters:
        errors.append("startup AGENTS.md exceeds 20000 characters")
    competing = startup.get("competing_files") if isinstance(startup.get("competing_files"), list) else []
    for name in competing:
        path = root / str(name)
        if path.exists() or path.is_symlink():
            errors.append(f"competing startup context exists: {name}")
    if startup.get("read_after_startup") != ["progress.md"]:
        errors.append("fresh sessions must read progress.md after startup")

    board_dir = kanban_root / str(slug)
    board_json_path = board_dir / "board.json"
    board = _load_json(board_json_path, errors, "board.json") if board_json_path.is_file() else {}
    if not board_json_path.is_file():
        errors.append("Kanban board.json is missing")
    if board.get("slug") != slug:
        errors.append("board slug mismatch")
    if board.get("project_id") != project_id:
        errors.append("board project_id mismatch")
    if board.get("default_workdir") != str(root):
        errors.append("board default_workdir mismatch")
    if board.get("archived") is not False:
        errors.append("board must be active")
    checks["board"] = {
        "slug": board.get("slug"),
        "project_id": board.get("project_id"),
        "default_workdir": board.get("default_workdir"),
    }

    row: dict[str, Any] | None = None
    if projects_db.is_file() and slug:
        try:
            con = sqlite3.connect(projects_db)
            con.row_factory = sqlite3.Row
            found = con.execute(
                "select id, slug, primary_path, board_slug, archived from projects where slug = ?",
                (slug,),
            ).fetchone()
            row = dict(found) if found else None
        except Exception as exc:
            errors.append(f"projects.db check failed: {exc}")
        finally:
            try:
                con.close()
            except Exception:
                pass
    if not row:
        errors.append("projects.db row missing")
    else:
        if row.get("id") != project_id:
            errors.append("projects.db project ID mismatch")
        if row.get("primary_path") != str(root):
            errors.append("projects.db primary_path mismatch")
        if row.get("board_slug") != slug:
            errors.append("projects.db board_slug mismatch")
        if row.get("archived"):
            errors.append("projects.db project is archived")
    checks["projects_db"] = row

    board_db = board_dir / "kanban.db"
    assigned_nonterminal: list[str] = []
    if not board_db.is_file():
        errors.append("Kanban database is missing")
    else:
        try:
            con = sqlite3.connect(board_db)
            placeholders = ",".join("?" for _ in NONTERMINAL_STATUSES)
            rows = con.execute(
                f"select id from tasks where status in ({placeholders}) and assignee is not null order by id",
                NONTERMINAL_STATUSES,
            ).fetchall()
            assigned_nonterminal = [str(item[0]) for item in rows]
        except Exception as exc:
            errors.append(f"Kanban task check failed: {exc}")
        finally:
            try:
                con.close()
            except Exception:
                pass
    if assigned_nonterminal:
        errors.append("assigned runnable Kanban cards exist: " + ", ".join(assigned_nonterminal))
    checks["assigned_nonterminal_cards"] = assigned_nonterminal

    policy = project.get("worker_policy") if isinstance(project.get("worker_policy"), dict) else {}
    eligible = policy.get("eligible_profiles") if isinstance(policy.get("eligible_profiles"), list) else []
    if policy.get("allowed_workspace_root") != str(root):
        errors.append("worker allowed_workspace_root must equal the bench path")
    if policy.get("forbid_other_project_benches") is not True:
        errors.append("worker policy must forbid other project benches")
    if not REQUIRED_FORBIDDEN_PATHS.issubset(set(policy.get("forbidden_paths") or [])):
        errors.append("worker forbidden_paths contract is incomplete")
    if "gbrain" not in set(policy.get("forbidden_mcp_servers") or []):
        errors.append("worker policy must forbid the gbrain MCP server")
    if not REQUIRED_ORCHESTRATOR_ONLY.issubset(set(policy.get("orchestrator_only_paths") or [])):
        errors.append("worker orchestrator_only_paths contract is incomplete")

    isolated_profiles: list[str] = []
    for profile in eligible:
        profile_dir = profiles_root / str(profile)
        if not profile_dir.is_dir():
            errors.append(f"worker profile missing: {profile}")
        elif _profile_exposes_gbrain(profile_dir):
            errors.append(f"worker profile {profile} exposes forbidden MCP server gbrain")
        else:
            isolated_profiles.append(str(profile))
    checks["eligible_profiles_without_gbrain"] = isolated_profiles

    dispatch_enabled = policy.get("dispatch_enabled") is True
    canary_required = policy.get("canary_required") is True
    canary_receipt = policy.get("canary_receipt")
    receipt_exists = False
    if dispatch_enabled:
        if canary_required:
            errors.append("dispatch cannot be enabled while canary_required is true")
        if not isinstance(canary_receipt, str) or not canary_receipt:
            errors.append("worker canary receipt is missing")
        else:
            receipt_path = (root / canary_receipt).resolve()
            try:
                receipt_path.relative_to(root)
            except ValueError:
                errors.append("worker canary receipt escapes the bench")
            else:
                receipt_exists = receipt_path.is_file()
                if not receipt_exists:
                    errors.append("worker canary receipt is missing")
    checks["canary_receipt_exists"] = receipt_exists
    checks["dispatch_enabled"] = dispatch_enabled
    checks["dispatch_authorized"] = dispatch_enabled and not canary_required and receipt_exists and not errors

    return {
        "status": "pass" if not errors else "fail",
        "bench": str(root),
        "checks": checks,
        "errors": errors,
    }


def require_dispatch_authorized(result: dict[str, Any]) -> None:
    if result.get("status") != "pass" or not result.get("checks", {}).get("dispatch_authorized"):
        raise DispatchNotAuthorized("worker dispatch is not authorized by the project alignment contract")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("bench", nargs="?", default=".")
    parser.add_argument("--require-dispatch", action="store_true")
    args = parser.parse_args()
    result = validate_alignment(Path(args.bench))
    if args.require_dispatch:
        try:
            require_dispatch_authorized(result)
        except DispatchNotAuthorized as exc:
            result["errors"].append(str(exc))
            result["status"] = "fail"
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if result["status"] == "pass" else 1


if __name__ == "__main__":
    sys.exit(main())
