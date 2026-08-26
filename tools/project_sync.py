#!/usr/bin/env python3
"""Deterministic synchronization for a complete Cortex project bench.

The synchronization engine is provider-neutral. A client must expose get_page
and put_page. The CLI adapter connects to the configured GBrain MCP server.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any, Callable, Protocol, Sequence


class SyncError(RuntimeError):
    """Base error for synchronization failures."""


class ConflictError(SyncError):
    """Local and canonical bodies both changed from the baseline."""


class StaleBaseError(SyncError):
    """Canonical state changed before promotion."""


class ExactReadbackError(SyncError):
    """Canonical read-back did not match the promoted body."""


class BinaryAssetNotSupported(SyncError):
    """GBrain MCP has no approved remote binary upload operation."""


class PageClient(Protocol):
    def get_page(self, slug: str) -> dict[str, Any]: ...

    def put_page(self, slug: str, content: str) -> dict[str, Any]: ...


def normalize_body(body: str) -> str:
    """Normalize transport line endings and require one terminal newline."""
    return body.replace("\r\n", "\n").replace("\r", "\n").rstrip("\n") + "\n"


def sha256_text(body: str) -> str:
    return hashlib.sha256(normalize_body(body).encode("utf-8")).hexdigest()


def classify(baseline: str, local: str, canonical: str) -> str:
    """Classify one page using its normalized B/L/C bodies."""
    baseline = normalize_body(baseline)
    local = normalize_body(local)
    canonical = normalize_body(canonical)
    if local == baseline and canonical == baseline:
        return "unchanged"
    if local != baseline and canonical == baseline:
        return "local_changed"
    if local == baseline and canonical != baseline:
        return "canonical_changed"
    if local == canonical:
        return "converged"
    return "conflict"


def _atomic_write(path: Path, content: str, mode: int | None = None) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    temporary_path = Path(temporary)
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as stream:
            stream.write(content)
            stream.flush()
            os.fsync(stream.fileno())
        if mode is not None:
            temporary_path.chmod(mode)
        os.replace(temporary_path, path)
    finally:
        temporary_path.unlink(missing_ok=True)


def _yaml_value(value: Any) -> str:
    if isinstance(value, bool):
        return "true" if value else "false"
    if value is None:
        return "null"
    if isinstance(value, (int, float)):
        return str(value)
    return json.dumps(str(value), ensure_ascii=False)


def compose_page(current: dict[str, Any], body: str) -> str:
    """Preserve lifecycle frontmatter without transport-generated fields."""
    frontmatter = current.get("frontmatter")
    frontmatter = frontmatter if isinstance(frontmatter, dict) else {}
    fields: list[tuple[str, Any]] = []
    if current.get("type"):
        fields.append(("type", current["type"]))
    generated = {"ingested_at", "ingested_via", "source_kind"}
    preferred = ("status", "phase", "template_revision")
    for key in preferred:
        if key in frontmatter:
            fields.append((key, frontmatter[key]))
    for key in sorted(frontmatter):
        if key not in generated and key not in preferred and key != "type":
            fields.append((key, frontmatter[key]))
    lines = ["---", *(f"{key}: {_yaml_value(value)}" for key, value in fields), "---"]
    return "\n".join(lines) + "\n" + normalize_body(body)


class SyncEngine:
    """Synchronize one complete project bench with one canonical page client."""

    def __init__(
        self,
        bench: Path | str,
        client: PageClient,
        *,
        now: Callable[[], str],
    ) -> None:
        self.bench = Path(bench).resolve()
        self.client = client
        self.now = now
        self.project_path = self.bench / "project.json"
        self.sync_path = self.bench / ".project/sync-state.json"
        self.project = json.loads(self.project_path.read_text(encoding="utf-8"))
        self.sync = json.loads(self.sync_path.read_text(encoding="utf-8"))
        if self.project.get("slug") != self.sync.get("slug"):
            raise SyncError("project.json and sync-state.json slugs differ")

    def _keys(self, keys: Sequence[str] | None) -> list[str]:
        configured = self.project.get("core_documents", {})
        selected = list(keys) if keys else list(configured)
        unknown = [key for key in selected if key not in configured]
        if unknown:
            raise SyncError("unknown document keys: " + ", ".join(unknown))
        return selected

    def _paths(self, key: str) -> tuple[Path, Path, str]:
        spec = self.project["core_documents"][key]
        state = self.sync["documents"][key]
        if spec["canonical_slug"] != state["canonical_slug"]:
            raise SyncError(f"{key}: canonical slug mismatch in metadata")
        return (
            self.bench / spec["local"],
            self.bench / state["snapshot_path"],
            spec["canonical_slug"],
        )

    def _read_triplet(self, key: str) -> dict[str, Any]:
        local_path, snapshot_path, slug = self._paths(key)
        local = normalize_body(local_path.read_text(encoding="utf-8"))
        baseline = normalize_body(snapshot_path.read_text(encoding="utf-8"))
        page = self.client.get_page(slug)
        canonical = normalize_body(str(page.get("compiled_truth", "")))
        return {
            "key": key,
            "slug": slug,
            "local_path": local_path,
            "snapshot_path": snapshot_path,
            "baseline": baseline,
            "local": local,
            "canonical": canonical,
            "page": page,
            "state": classify(baseline, local, canonical),
        }

    def _result(self, item: dict[str, Any], *, action: str) -> dict[str, Any]:
        page = item["page"]
        return {
            "state": item["state"],
            "action": action,
            "canonical_slug": item["slug"],
            "baseline_sha256": sha256_text(item["baseline"]),
            "local_sha256": sha256_text(item["local"]),
            "canonical_body_sha256": sha256_text(item["canonical"]),
            "canonical_content_hash": page.get("content_hash"),
            "canonical_updated_at": page.get("updated_at"),
            "source_id": page.get("source_id"),
        }

    def _advance_baseline(self, key: str, canonical: str, page: dict[str, Any]) -> None:
        _, snapshot_path, _ = self._paths(key)
        canonical = normalize_body(canonical)
        _atomic_write(snapshot_path, canonical, mode=0o444)
        state = self.sync["documents"][key]
        state["baseline_sha256"] = sha256_text(canonical)
        state["canonical_content_hash"] = page.get("content_hash")
        self.sync["refreshed_at"] = self.now()
        self.sync["refresh_method"] = "gbrain-mcp-get_page-exact-body"
        _atomic_write(self.sync_path, json.dumps(self.sync, indent=2) + "\n", mode=0o644)

    def status(self, keys: Sequence[str] | None = None) -> dict[str, dict[str, Any]]:
        output: dict[str, dict[str, Any]] = {}
        for key in self._keys(keys):
            item = self._read_triplet(key)
            output[key] = self._result(item, action="none")
        return output

    def refresh(self, keys: Sequence[str] | None = None) -> dict[str, dict[str, Any]]:
        items = [self._read_triplet(key) for key in self._keys(keys)]
        conflicts = [item["key"] for item in items if item["state"] == "conflict"]
        if conflicts:
            raise ConflictError("refresh blocked by conflicts: " + ", ".join(conflicts))

        output: dict[str, dict[str, Any]] = {}
        for item in items:
            state = item["state"]
            action = "none"
            recorded = self.sync["documents"][item["key"]]
            metadata_changed = (
                recorded.get("canonical_content_hash")
                != item["page"].get("content_hash")
                or recorded.get("baseline_sha256")
                != sha256_text(item["canonical"])
            )
            if state == "canonical_changed":
                _atomic_write(item["local_path"], item["canonical"], mode=0o644)
                self._advance_baseline(item["key"], item["canonical"], item["page"])
                item["local"] = item["canonical"]
                item["baseline"] = item["canonical"]
                action = "refreshed"
            elif state == "converged":
                self._advance_baseline(item["key"], item["canonical"], item["page"])
                item["baseline"] = item["canonical"]
                action = "baseline_advanced"
            elif state == "local_changed":
                action = "preserved_local_change"
            elif state == "unchanged" and metadata_changed:
                _atomic_write(item["local_path"], item["canonical"], mode=0o644)
                self._advance_baseline(item["key"], item["canonical"], item["page"])
                item["local"] = item["canonical"]
                item["baseline"] = item["canonical"]
                action = "metadata_refreshed"
            output[item["key"]] = self._result(item, action=action)
        return output

    def promote(self, keys: Sequence[str]) -> dict[str, dict[str, Any]]:
        selected = self._keys(keys)
        if len(selected) != 1:
            raise SyncError("promote accepts exactly one document per supervised operation")
        key = selected[0]
        item = self._read_triplet(key)
        state = item["state"]
        if state == "conflict":
            raise ConflictError(f"{key}: local and canonical bodies both changed")
        if state == "canonical_changed":
            raise StaleBaseError(f"{key}: canonical body changed; refresh before promotion")
        if state == "unchanged":
            return {key: self._result(item, action="none")}
        if state == "converged":
            self._advance_baseline(key, item["canonical"], item["page"])
            item["baseline"] = item["canonical"]
            return {key: self._result(item, action="baseline_advanced")}

        current = self.client.get_page(item["slug"])
        current_body = normalize_body(str(current.get("compiled_truth", "")))
        if current_body != item["baseline"]:
            raise StaleBaseError(f"{key}: canonical body changed during promotion preflight")

        payload = compose_page(current, item["local"])
        self.client.put_page(item["slug"], payload)
        readback = self.client.get_page(item["slug"])
        readback_body = normalize_body(str(readback.get("compiled_truth", "")))
        if readback_body != item["local"]:
            raise ExactReadbackError(f"{key}: promoted body failed exact read-back")

        self._advance_baseline(key, readback_body, readback)
        item.update(
            baseline=readback_body,
            canonical=readback_body,
            page=readback,
            state="unchanged",
        )
        return {key: self._result(item, action="promoted")}

    def promote_asset(self, path: Path | str) -> None:
        raise BinaryAssetNotSupported(
            f"binary promotion blocked for {Path(path)}: GBrain MCP file_upload is local-only"
        )


def durability_report(bench: Path, pages: dict[str, dict[str, Any]]) -> dict[str, Any]:
    """Report canonical layers separately without claiming equivalence."""

    def command(*args: str) -> dict[str, Any]:
        run = subprocess.run(args, text=True, capture_output=True, check=False)
        return {
            "returncode": run.returncode,
            "stdout": run.stdout.strip(),
            "stderr": run.stderr.strip(),
        }

    project = json.loads((bench / "project.json").read_text(encoding="utf-8"))
    cortex_path = Path(project["cortex_record_path"])
    page_states = {
        key: {
            "slug": page.get("slug"),
            "source_id": page.get("source_id"),
            "content_hash": page.get("content_hash"),
            "updated_at": page.get("updated_at"),
            "deleted_at": page.get("deleted_at"),
        }
        for key, page in pages.items()
    }
    return {
        "gbrain_pages": page_states,
        "cortex_disk": {
            "record_path": str(cortex_path),
            "exists": cortex_path.is_dir(),
            "filesystem_access": "read-only-for-hermes",
        },
        "canonical_git": {
            "head": command("git", "-C", "/cortex", "rev-parse", "HEAD"),
            "worktree": command("git", "-C", "/cortex", "status", "--short"),
        },
        "remote_backup": {
            "master": command("git", "-C", "/cortex", "ls-remote", "origin", "refs/heads/master")
        },
        "derived_index": {
            key: {
                "source_id": page.get("source_id"),
                "content_hash": page.get("content_hash"),
                "updated_at": page.get("updated_at"),
            }
            for key, page in pages.items()
        },
    }


__all__ = [
    "BinaryAssetNotSupported",
    "ConflictError",
    "ExactReadbackError",
    "StaleBaseError",
    "SyncEngine",
    "SyncError",
    "classify",
    "compose_page",
    "durability_report",
    "normalize_body",
]
