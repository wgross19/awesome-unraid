---
type: project
title: Awesome Unraid — Plan
phase: P0
status: active
template_revision: focused-workers-v2
---

# Plan — Awesome Unraid

## Task tree

```text
Awesome Unraid
├── P0: Define scope, authority, and acceptance
├── P1: Prepare the complete bench, canonical record, bindings, and board
├── P2: Execute the approved catalog work
├── P3: Run independent verification and correction
├── P4: Promote accepted outcomes and reconcile state
└── P5: Preserve evidence and close
```

## Phase and card map

| Phase | Task ID | Lane | Workspace path | Dependencies | Status | Acceptance evidence | Human gate |
|---|---|---|---|---|---|---|---|
| P0 | `t_<id>` | orchestrator | `/workspace/projects/awesome-unraid` | — | proposed | | |

## Graph-construction receipt

- Cards created unassigned
- Dependencies encoded before assignment
- Human gates typed `needs_input`
- Completion subscriptions verified
- Dry run returned `spawned: []`
- Only intended roots appear as unassigned

## Lane and tool contract

| Lane | Exact tools | Forbidden tools | Writable surface | Artifact path | Review path |
|---|---|---|---|---|---|
| Researcher | cited research | terminal, browser, MCP unless separately approved | project bench | `artifacts/` or `_scratch/` | downstream review |
| Builder | terminal, file, todo | MCP and unapproved external tools | project-owned worktree | commit plus attachment or recovery | verifier |
| Verifier | terminal, file, vision, todo | MCP and original implementation | project bench or verifier worktree | verdict artifact | complete or repair |

## Canonical synchronization

Before any canonical promotion, compare the last baseline, local working copy, and current Cortex page. Concurrent local and canonical changes stop promotion until reconciled. The orchestrator alone calls GBrain MCP and verifies exact read-back.

## Parallel-safety map

- `app/` catalog content — serialized (shared catalog)
- External repo sync — serialized (PR-based)
- Live Unraid host — serialized (production)

## Rollback and stop conditions

- Stop if a catalog publication is attempted without human approval.
- Stop if the live Unraid stack would be mutated without separate authorization.
- Rollback via git revert on the affected repo; never rewrite history.

## Closeout

Reconcile the live board, preserve evidence, promote accepted knowledge, verify exact read-back, report Git and derived-index state separately, classify lessons, and sweep only recoverable project-local scratch.
