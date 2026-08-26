---
type: project
title: Awesome Unraid — Overview
phase: P0
status: active
template_revision: focused-workers-v2
---

# Awesome Unraid

## Status

- **Status:** active
- **Phase:** P0
- **Project slug:** `awesome-unraid`
- **Complete workspace bench:** `/workspace/projects/awesome-unraid`
- **Canonical Cortex record:** `/cortex/projects/awesome-unraid`
- **Kanban board:** `awesome-unraid`
- **Hermes project ID:** `p_06e7bccc`

## Purpose

Central Unraid catalog for the broader AIO portfolio. Source of truth for CA-facing XML and icon assets.

## Problem

Catalog content (CA XML, icons) was scattered and not tied to a project. There was no single source of truth for user-facing catalog metadata.

## Observable outcome

A single catalog repo that app repos sync into via PRs, keeping template, icon, and catalog metadata aligned with the apps they represent.

## Requirements

- Source of truth for CA-facing XML and icon assets.
- External repo sync flows create/update PRs rather than pushing directly to protected branches.
- Template, icon, and catalog metadata aligned with the app repos they represent.
- No stale or placeholder catalog content.

## Non-goals

- App-specific runtime logic (stays in each app repo).
- GBrain/Cortex integration for the catalog.
- Public sharing before personal AIO images are working.

## Acceptance criteria

- The `awesome-unraid` bench holds the catalog and its docs.
- Catalog content is accurate, stable, and user-facing.
- External sync flows use PRs, not direct pushes.
- Catalog metadata stays aligned with app repos.

## Risks and constraints

- Catalog publication is human-gated.
- Live Unraid deployment must not be mutated without separate authorization.

## Current architecture

```text
/workspace/projects/awesome-unraid = complete operational project
/workspace/projects/awesome-unraid/app = catalog (git working copy)
```

- **Selected lanes:** researcher, builder, verifier
- **Canonical writer:** supervised Hermes orchestrator through GBrain MCP
- **Worker root:** `/workspace/projects/awesome-unraid`

## Human gates

- Catalog publication.
- Unraid deployment.

## Timeline

- **2026-08-25** | Bench created; `awesome-unraid` repo moved under `projects/awesome-unraid/app`.

## Entry point

Local startup order: `AGENTS.md` → `progress.md` → relevant `overview.md` and `plan.md` sections → evidence as needed.

Canonical links after instantiation: [[projects/awesome-unraid/agents|instructions]], [[projects/awesome-unraid/progress|progress]], [[projects/awesome-unraid/plan|plan]], [[projects/awesome-unraid/decisions|decisions]], and [[projects/awesome-unraid/execution_log|execution log]].
