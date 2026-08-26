---
type: project
title: Awesome Unraid — Decisions
phase: P0
status: active
template_revision: focused-workers-v2
---

# Decisions — Awesome Unraid

Record durable choices and their consequences. Keep material timeline milestones in `overview.md`.

## 2026-08-25 — Bench consolidation

- **Decision:** Consolidate the `awesome-unraid` catalog into a dedicated bench under `/workspace/projects/awesome-unraid`, with the git working copy at `app/`.
- **Why:** All projects should live under the `projects/` directory; the catalog repo was loose at `/workspace` root.
- **Consequences:** The bench now holds the catalog and its docs. The repo remains the source of truth for CA-facing XML and icon assets.
- **Evidence / Kanban task:** `t_<id>`

## Required architecture decisions

### Project identity and workspace

- One exact slug across Cortex, bench, `projects.db`, board, and metadata
- Complete operational root at `/workspace/projects/awesome-unraid`

### Canonical synchronization

- Last-verified Cortex baselines and hashes
- Stale-base and concurrent-change behavior
- Orchestrator-only GBrain MCP promotion

### Worker authority

- Selected lanes and exact tools
- Allowed files and surfaces
- Explicit worker absence of GBrain MCP

### Artifacts and recovery

- Durable artifact paths
- Scratch and worktree recovery
- Cleanup only after evidence is durable

### Review and promotion

- Independent verifier topology
- Parallel-safety boundaries
- Additive correction evidence
- Reviewed rollback without rewriting history
