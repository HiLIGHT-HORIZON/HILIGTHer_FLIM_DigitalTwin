# Audit Matrix

This file tracks human-audited or pending-audit subsystems without overloading the architecture intent map.

| Subsystem | Authoritative references | Audit status | Human-verified date | Open issues / drift notes |
| :--- | :--- | :--- | :--- | :--- |
| Backend precision workflow | `docs/architecture_intent.md`, `docs/manual/apis.html`, `python/backend/service_api.py` | Pending | - | Reconfirm conditional precision semantics and documented service/API behavior after future precision changes. |
| Physics and maths audit | `docs/physics_maths_audit.md`, `docs/manual/maths.html`, `python/backend/twin_engine.py`, `python/backend/event_driven.py`, `python/backend/models.py` | In review | - | Preliminary Codex audit prepared. Human scientific sign-off still required before treating maths/physics implementation as audited. |
| Dead-time correction semantics | `docs/next_milestones.md`, `docs/feature_request_next_phase.md`, `docs/physics_maths_audit.md`, `python/backend/twin_engine.py`, `python/backend/event_driven.py` | Planned | - | Future work. Scientific validation is required before any correction-aware Fisher or reporting semantics are treated as complete. |
| Pixellated detector modelling | `docs/next_milestones.md`, `docs/feature_request_next_phase.md`, `docs/architecture_intent.md`, `python/backend/event_driven.py`, `python/backend/models.py` | Planned | - | Future work. Human review is required to validate detector-topology semantics and the boundary between abstraction and physical realism. |
| Digital frequency-domain workflow | `docs/next_milestones.md`, `docs/feature_request_next_phase.md`, `docs/manual/maths.html`, `python/backend/twin_engine.py`, `python/backend/models.py` | Planned | - | Future work. Scientific review is required before digital FD outputs and sine-wave excitation semantics are treated as complete or exposed publicly. |
| Optimisation workflow | `docs/architecture_intent.md`, `docs/manual/apis.html`, `python/backend/service_api.py`, `python/backend/twin_engine.py` | Pending | - | Keep optimisation objective definitions and integrated workflow docs synchronized. |
| Session persistence | `docs/architecture_intent.md`, `docs/manual/apis.html`, `python/backend/storage.py`, `python/backend/service_api.py` | Pending | - | Verify save/load semantics remain consistent across desktop, HTTP, and MCP surfaces. |
| Frontend and API alignment | `README.md`, `docs/manual/apis.html`, `python/frontend/src/App.jsx`, `python/backend/main.py` | Pending | - | Legacy compatibility routes still exist; keep frontend assumptions and API docs aligned. |
| MCP server and prompts | `docs/manual/mcp.html`, `docs/manual/apis.html`, `python/mcp_server.py`, `python/mcp_prompts.py` | Pending | - | Confirm documented tools and prompts exactly match implementation after MCP changes. |
| Desktop automation API | `docs/manual/apis.html`, `python/gui/automation_api.py`, `python/gui/main_window.py` | Pending | - | Recheck exposed actions and running-session assumptions when automation changes. |
| Histogram and visual control synchronization | `AGENTS.md`, `.agent/tasks/fix_histogram_sync.md`, `python/gui/widgets/` | Pending | - | Current known task: bidirectional sync between histogram lines and numeric spinners. |
