---
type: project
title: Awesome Unraid — Project Instructions
phase: P0
status: active
template_revision: focused-workers-v2
---

# Awesome Unraid — Project Instructions

## Identity and boundary

- **Project slug:** `awesome-unraid`
- **Complete workspace bench:** `/workspace/projects/awesome-unraid`
- **Canonical Cortex record:** `/cortex/projects/awesome-unraid`
- **Hermes project ID:** `p_06e7bccc`
- **Kanban board:** `awesome-unraid`

This workspace bench is the sole operational root for Hermes and scoped workers. Keep every relevant working document, code file, test, dataset, evidence item, artifact, and project-local scratch inside it.

Cortex is the accepted canonical record. GBrain is its sole read-write owner. Hermes has read-only Cortex filesystem access. Only the supervised orchestrator promotes accepted Markdown through GBrain MCP and verifies exact read-back.

## Required local documents

```text
AGENTS.md
overview.md
plan.md
progress.md
decisions.md
execution_log.md
```

Read local `progress.md` first after these instructions, then only the relevant sections of `overview.md`, `plan.md`, `decisions.md`, and `execution_log.md`.

Keep changing state out of `AGENTS.md`. Use this file only for stable identity, authority, scope, tools, and gates.

## Canonical synchronization

The bench will store last-verified Cortex snapshots under `.project/canonical/` and hashes under `.project/sync-state.json`.

For every canonical page compare:

```text
B = last verified canonical baseline
L = current local working copy
C = current Cortex page
```

If both `L` and `C` changed from `B`, stop and reconcile. Before promotion, fetch `C` again and confirm it still matches the base. After `put_page`, read back the exact page before refreshing the local baseline.

Report GBrain page state, Cortex disk state, Git commit, remote backup, and derived-index state separately.

## Worker boundary

Scoped workers:

- work only inside this bench or a project-owned worktree;
- receive only the tools and files needed for their assigned card;
- do not receive or call GBrain MCP;
- do not write Cortex, `.project/canonical/`, `.project/sync-state.json`, `project.json`, `projects.db`, another project, credentials, or unapproved production systems;
- preserve original evidence and return exact artifact paths, changed files, tests, and residual risk.

The orchestrator reviews and accepts evidence, reconciles state, performs canonical promotion, and updates project bindings.

## Kanban and dispatch

Create cards unassigned and encode dependencies before assignment. Human and host actions use `needs_input`. Verify subscriptions and require dry-run `spawned: []`. Planning, dependency promotion, phase approval, or preparation does not authorize dispatch.

Use only required lanes:

- **Researcher:** cited research inside the bench; no terminal, browser, or MCP unless a separately approved profile says otherwise.
- **Builder:** implementation and tests inside a project-owned worktree or explicitly authorized bench paths; no MCP.
- **Verifier:** independent acceptance reproduction; no original implementation or MCP.
- **Operator:** optional and separately authorized for interactive or production action.

Parallel work requires disjoint mutable surfaces. Serialize shared files, services, canonical pages, credentials, external accounts, and production systems.

## Evidence and cleanup

Keep durable evidence under `artifacts/`, project documents, or committed project work. Put disposable work under `_scratch/`. Do not clean scratch or worktrees until recovery is proven.

At closeout, reconcile the board, promote accepted knowledge, verify read-back, preserve artifacts, classify lessons, and sweep only project-local recoverable scratch.

## Project-specific constraints

- **Purpose:** Central Unraid catalog for the broader AIO portfolio. Source of truth for CA-facing XML and icon assets.
- **Selected lanes and exact tools:** researcher (cited research), builder (terminal, file, todo), verifier (terminal, file, vision, todo).
- **Writable files and surfaces:** this bench and the `app/` working copy (`/workspace/projects/awesome-unraid/app`).
- **Forbidden surfaces:** Cortex filesystem, GBrain MCP, project metadata, credentials, production systems, and the live Unraid host unless separately authorized.
- **Required tests and evidence:** catalog content accuracy, template/icon/catalog metadata alignment, and external repo sync via PRs.
- **Human gates:** catalog publication and Unraid deployment are human-gated.
- **One next action source:** local `progress.md`
