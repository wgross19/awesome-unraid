#!/usr/bin/env python3
"""Supervised GBrain MCP adapter and CLI for project bench synchronization."""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Sequence

try:
    from tools.project_sync import (
        BinaryAssetNotSupported,
        SyncEngine,
        SyncError,
        durability_report,
    )
except ModuleNotFoundError:
    from project_sync import (  # type: ignore[no-redef]
        BinaryAssetNotSupported,
        SyncEngine,
        SyncError,
        durability_report,
    )


def parse_mcp_result(result: Any) -> dict[str, Any]:
    for part in getattr(result, "content", []):
        if getattr(part, "type", None) == "text":
            payload = json.loads(part.text)
            if isinstance(payload, dict):
                return payload
    raise RuntimeError("MCP result has no JSON object text part")


class HermesGBrainClient:
    """Synchronous page client backed by Hermes's configured GBrain MCP."""

    def __init__(self, server_name: str = "gbrain") -> None:
        source_root = Path(os.environ.get("HERMES_SOURCE_ROOT", "/opt/hermes"))
        if str(source_root) not in sys.path:
            sys.path.insert(0, str(source_root))
        try:
            from hermes_cli.mcp_config import _get_mcp_servers, _resolve_mcp_server_config
            from tools.mcp_tool import (
                _connect_server,
                _ensure_mcp_loop,
                _run_on_mcp_loop,
                _stop_mcp_loop_if_idle,
            )
        except ImportError as exc:
            raise RuntimeError(
                "Hermes MCP runtime is unavailable; run with /opt/hermes/.venv/bin/python"
            ) from exc

        servers = _get_mcp_servers()
        if server_name not in servers:
            raise RuntimeError(f"MCP server is not configured: {server_name}")
        self._connect_server = _connect_server
        self._ensure_loop = _ensure_mcp_loop
        self._run = _run_on_mcp_loop
        self._stop_loop = _stop_mcp_loop_if_idle
        self._config = _resolve_mcp_server_config(servers[server_name])
        self._server_name = server_name
        self._task = None
        self._ensure_loop()
        self._task = self._run(self._connect(), timeout=60)

    async def _connect(self) -> Any:
        return await self._connect_server(
            f"project-sync-{os.getpid()}",
            self._config,
        )

    async def _call(self, tool: str, arguments: dict[str, Any]) -> dict[str, Any]:
        if self._task is None:
            raise RuntimeError("GBrain MCP client is closed")
        result = await self._task.session.call_tool(tool, arguments)
        return parse_mcp_result(result)

    def get_page(self, slug: str) -> dict[str, Any]:
        return self._run(self._call("get_page", {"slug": slug}), timeout=60)

    def put_page(self, slug: str, content: str) -> dict[str, Any]:
        return self._run(
            self._call("put_page", {"slug": slug, "content": content}),
            timeout=90,
        )

    def close(self) -> None:
        if self._task is not None:
            self._run(self._task.shutdown(), timeout=30)
            self._task = None
        self._stop_loop()

    def __enter__(self) -> "HermesGBrainClient":
        return self

    def __exit__(self, *_: object) -> None:
        self.close()


def _documents(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--document",
        action="append",
        choices=("agents", "overview", "plan", "progress", "decisions", "execution_log"),
        help="Limit the operation to one or more document keys.",
    )
    parser.add_argument("--bench", default=".", help="Complete project bench path.")
    parser.add_argument("--server", default="gbrain", help="Configured MCP server name.")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Supervised deterministic Cortex project synchronization."
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    status = subparsers.add_parser("status", help="Read and classify B/L/C state.")
    _documents(status)

    refresh = subparsers.add_parser(
        "refresh",
        help="Refresh canonical-only changes and preserve local-only work.",
    )
    _documents(refresh)

    promote = subparsers.add_parser(
        "promote",
        help="Promote exactly one reviewed local Markdown page.",
    )
    promote.add_argument("--document", action="append", required=True, choices=(
        "agents", "overview", "plan", "progress", "decisions", "execution_log"
    ))
    promote.add_argument(
        "--approve",
        action="store_true",
        required=True,
        help="Confirm supervised canonical mutation for this one page.",
    )
    promote.add_argument("--bench", default=".")
    promote.add_argument("--server", default="gbrain")

    report = subparsers.add_parser(
        "report",
        help="Report GBrain, Cortex disk, Git, remote, and index state separately.",
    )
    _documents(report)

    asset = subparsers.add_parser(
        "asset-policy",
        help="Report the current binary-asset promotion policy.",
    )
    asset.add_argument("path")
    asset.add_argument("--bench", default=".")
    return parser


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _page_keys(bench: Path, selected: Sequence[str] | None) -> list[str]:
    project = json.loads((bench / "project.json").read_text(encoding="utf-8"))
    return list(selected) if selected else list(project["core_documents"])


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    bench = Path(args.bench).resolve()

    if args.command == "asset-policy":
        payload = {
            "status": "blocked",
            "path": str((bench / args.path).resolve()),
            "reason": "GBrain MCP file_upload is local-only",
            "required_path": "separately approved GBrain-owned binary upload capability",
        }
        print(json.dumps(payload, indent=2, sort_keys=True))
        return 0

    try:
        with HermesGBrainClient(args.server) as client:
            engine = SyncEngine(bench, client, now=utc_now)
            if args.command == "status":
                result: dict[str, Any] = {
                    "operation": "status",
                    "documents": engine.status(args.document),
                }
            elif args.command == "refresh":
                result = {
                    "operation": "refresh",
                    "documents": engine.refresh(args.document),
                }
            elif args.command == "promote":
                result = {
                    "operation": "promote",
                    "documents": engine.promote(args.document),
                }
            else:
                keys = _page_keys(bench, args.document)
                project = json.loads((bench / "project.json").read_text(encoding="utf-8"))
                pages = {
                    key: client.get_page(project["core_documents"][key]["canonical_slug"])
                    for key in keys
                }
                result = {
                    "operation": "report",
                    "sync": engine.status(keys),
                    "durability": durability_report(bench, pages),
                }
        print(json.dumps(result, indent=2, sort_keys=True))
        return 0
    except (SyncError, RuntimeError, OSError, json.JSONDecodeError) as exc:
        print(json.dumps({
            "status": "blocked",
            "error": type(exc).__name__,
            "message": str(exc),
        }, indent=2, sort_keys=True), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
