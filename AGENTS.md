# HILIGHTer Agent Contract

This file is the canonical cross-agent project contract for this repository.

All agent-specific entrypoints must defer to this file rather than redefining project policy:

- `AGENTS.md` for Codex and generic agent tooling
- `CLAUDE.md` for Claude-oriented discovery
- `.agent/rules/agent-contract.md` for Google Antigravity

## Product Identity

HILIGHTer is a Python-first digital twin for FLIM instrument design, precision benchmarking, synthetic validation, optimisation, and automation.

Project defaults:

- desktop-first operator workflow
- simulation-first product scope
- one shared backend engine reused across desktop, HTTP, automation, and MCP
- documentation treated as an actively maintained interface, not an afterthought

## Sources of Truth

Treat the following as the authoritative sources for project behavior and architecture:

- `README.md`
- `docs/architecture_intent.md`
- `docs/audit_matrix.md`
- `docs/manual/apis.html`
- `docs/manual/mcp.html`
- `python/metadata.py`
- `python/backend/service_api.py`
- `python/mcp_server.py`
- `python/mcp_prompts.py`

If a task changes public behavior, architecture intent, MCP semantics, or scientific meaning, update the relevant source-of-truth files in the same task.

## Core Architecture Rules

1. One engine
   - Shared numerical behavior belongs in the backend engine and service layer, not duplicated across UI or transports.

2. Service-first orchestration
   - `DigitalTwinService` is the canonical orchestration surface.
   - HTTP, MCP, desktop automation, and desktop UI should reflect service-layer semantics.

3. UI/compute separation
   - Do not place scientific compute logic directly inside Qt callbacks.
   - Widgets may trigger workflows and render results, but backend logic must remain reusable.

4. Simulation-first scope
   - The maintained project is simulation- and optimisation-focused.
   - Real-data SDT import is out of scope unless explicitly reintroduced by the human.

5. Documentation alignment
   - API docs, MCP docs, and architecture intent must remain aligned with the implemented codebase.
   - Do not leave silent drift between docs and code.

## MCP Rules

MCP-facing descriptions must match the actual implementation.

When changing MCP behavior, verify and align all of:

- tool definitions in `python/mcp_server.py`
- prompt definitions in `python/mcp_prompts.py`
- service behavior in `python/backend/service_api.py`
- manual documentation in `docs/manual/mcp.html`
- API positioning in `docs/manual/apis.html`

Do not document tools, prompts, or workflows that are not actually implemented.

## Guarded Change Areas

The following areas require explicit intent checks before changing behavior:

- precision semantics and Fisher reporting
- optimisation objective definitions and workflow meaning
- persistence and session semantics
- MCP tool, prompt, and workflow contracts
- GUI behavior when it changes scientific interpretation rather than presentation only

Before changing one of these areas:

1. Determine whether the change is implementation-only or semantic.
2. If semantic or publicly visible, update the corresponding docs in the same task.
3. If the change alters scientific meaning, assumptions, or interpretation, require explicit human confirmation before proceeding.

## Before and After Change Protocol

Before any substantial change:

- identify which source-of-truth files govern the affected behavior
- check whether the task touches a guarded area
- check whether an existing workflow under `.agent/workflows/` applies

After any substantial change:

- update affected docs and contracts in the same task
- verify cross-agent files do not contradict each other
- run relevant checks before considering the work complete

## Mutation and Git Rules

- No automatic commits or pushes unless explicitly requested by the human.
- Do not invent or silently introduce versioning workflows.
- Do not treat task prompts as standing policy.
- Do not make destructive changes without explicit authorization.

## Verification Expectations

Before task completion, run the most relevant lightweight verification available for the change. Use what applies:

- Python compile checks
- targeted `pytest` runs
- MCP smoke checks
- static grep checks for contract/doc consistency
- offscreen or smoke startup checks for desktop/UI tasks

If verification could not be run, say so explicitly.

## Audit Loop

Audit state lives in `docs/audit_matrix.md`, not in the architecture map.

Use the audit matrix to track:

- subsystem
- authoritative references
- audit status
- human verification date
- open drift or follow-up notes

Do not mark a subsystem as human-audited without explicit human confirmation.

## Workflow Entry Points

Reusable Antigravity workflows live under `.agent/workflows/`.

Recommended use:

- `audit.md` for architecture/doc/code auditing
- `docs-sync.md` for behavior changes that require doc alignment
- `mcp-change.md` for MCP tools/prompts/resources changes
- `gui-behavior.md` for Qt behavior changes and callback/compute separation

Task files under `.agent/tasks/` are overlays for specific work items. They are not the global contract.
