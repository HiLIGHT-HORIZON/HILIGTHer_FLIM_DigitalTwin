"""Minimal stdio MCP server for HILIGHTer.

The server is intentionally small and delegates real work to
`backend.service_api.DigitalTwinService`. Tool, resource, and prompt metadata
should stay aligned with the service layer and `mcp_prompts.py`.
"""

import contextlib
import json
import os
import sys
from typing import Any, Dict

sys.path.insert(0, os.path.dirname(__file__))

from metadata import get_version


_SERVICE = None
_PROMPTS = None


def get_service():
    """Lazily construct one shared service instance for the MCP process."""
    global _SERVICE
    if _SERVICE is None:
        from backend.service_api import DigitalTwinService
        _SERVICE = DigitalTwinService()
    return _SERVICE


def get_prompts_map():
    """Lazily load MCP prompt definitions."""
    global _PROMPTS
    if _PROMPTS is None:
        from mcp_prompts import get_prompts
        _PROMPTS = get_prompts()
    return _PROMPTS


SERVER_INFO = {"name": "hilighter-digital-twin-mcp", "version": get_version()}


def _read_message():
    line = sys.stdin.readline()
    if not line:
        return None
    try:
        return json.loads(line)
    except json.JSONDecodeError:
        return None


def _write_message(message: Dict[str, Any]):
    sys.stdout.write(json.dumps(message) + "\n")
    sys.stdout.flush()


def _success(msg_id, result):
    _write_message({"jsonrpc": "2.0", "id": msg_id, "result": result})


def _error(msg_id, code, message):
    _write_message({"jsonrpc": "2.0", "id": msg_id, "error": {"code": code, "message": message}})


def _tool_definitions():
    """Return MCP tool metadata mirrored from the current service capabilities."""
    return [
        {
            "name": "get_status",
            "description": "Return backend readiness, current engine summary, and data availability.",
            "inputSchema": {"type": "object", "properties": {}},
        },
        {
            "name": "get_config",
            "description": "Return the current Digital Twin configuration.",
            "inputSchema": {"type": "object", "properties": {}},
        },
        {
            "name": "update_config",
            "description": "Patch the current Digital Twin configuration.",
            "inputSchema": {
                "type": "object",
                "properties": {"config_patch": {"type": "object"}},
                "required": ["config_patch"],
            },
        },
        {
            "name": "run_precision",
            "description": "Run theory and optional Monte Carlo precision analysis.",
            "inputSchema": {
                "type": "object",
                "properties": {"config_patch": {"type": "object"}},
            },
        },
        {
            "name": "run_optimisation",
            "description": "Run the integrated optimisation workflow across detection gates, excitation profile, or both, with Fisher Information or Fisher-throughput objectives.",
            "inputSchema": {
                "type": "object",
                "properties": {"config_patch": {"type": "object"}},
            },
        },
        {
            "name": "simulate_basic",
            "description": "Generate a basic synthetic dataset and fit it.",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "a": {"type": "number"},
                    "tau1": {"type": "number"},
                    "tau2": {"type": "number"},
                    "b": {"type": "number"},
                    "res": {"type": "integer"},
                    "fit_method": {"type": "string"},
                },
            },
        },
        {
            "name": "simulate_advanced",
            "description": "Generate an advanced instrument simulation and fit it.",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "a": {"type": "number"},
                    "tau1": {"type": "number"},
                    "tau2": {"type": "number"},
                    "b": {"type": "number"},
                    "res": {"type": "integer"},
                    "fit_method": {"type": "string"},
                },
            },
        },
        {
            "name": "get_data_summary",
            "description": "Return current raw-data and result-map summaries.",
            "inputSchema": {"type": "object", "properties": {}},
        },
        {
            "name": "get_results_snapshot",
            "description": "Return current tau, amplitude, background, chi2, and summary payloads.",
            "inputSchema": {"type": "object", "properties": {}},
        },
        {
            "name": "get_tau_map",
            "description": "Return the current tau map only.",
            "inputSchema": {"type": "object", "properties": {}},
        },
        {
            "name": "get_phasor_map",
            "description": "Return the current phasor map for a harmonic.",
            "inputSchema": {
                "type": "object",
                "properties": {"harmonic": {"type": "integer"}},
            },
        },
        {
            "name": "get_theoretical_locus",
            "description": "Return the theoretical phasor locus.",
            "inputSchema": {"type": "object", "properties": {}},
        },
        {
            "name": "get_pixel_analysis",
            "description": "Return one pixel decay, fit, and estimated lifetime.",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "y": {"type": "integer"},
                    "x": {"type": "integer"},
                },
                "required": ["y", "x"],
            },
        },
        {
            "name": "get_diagnostics_snapshot",
            "description": "Return time vector, gates, IRF, and reference PDF for the current instrument.",
            "inputSchema": {
                "type": "object",
                "properties": {"tau_ref": {"type": "number"}},
            },
        },
        {
            "name": "get_gui_schema",
            "description": "Return the declarative GUI schema for software-driven frontends.",
            "inputSchema": {"type": "object", "properties": {}},
        },
        {
            "name": "save_session",
            "description": "Persist the current state and available data under a session identifier.",
            "inputSchema": {
                "type": "object",
                "properties": {"session_id": {"type": "string"}},
                "required": ["session_id"],
            },
        },
        {
            "name": "load_session",
            "description": "Restore a previously saved session.",
            "inputSchema": {
                "type": "object",
                "properties": {"session_id": {"type": "string"}},
                "required": ["session_id"],
            },
        },
        {
            "name": "ingest_instrument_profile_source",
            "description": "Read a local PDF/file or webpage, extract instrument specifications, and create/save/apply an instrument profile. Intended for use with an LLM that reviews the extracted source text and refines the profile patch.",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "source": {"type": "string"},
                    "profile_name": {"type": "string"},
                    "config_patch": {"type": "object"},
                    "description": {"type": "string"},
                    "apply_profile": {"type": "boolean"},
                    "save_profile": {"type": "boolean"},
                    "max_chars": {"type": "integer"},
                },
                "required": ["source", "profile_name"],
            },
        },
        {
            "name": "list_vendor_sources",
            "description": "List the vendor documentation files available under docs/vendors_info for LLM-guided instrument profile creation.",
            "inputSchema": {"type": "object", "properties": {}},
        },
        {
            "name": "read_vendor_source",
            "description": "Read one vendor document from docs/vendors_info, extract text, and suggest an instrument-profile patch.",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "source_name": {"type": "string"},
                    "max_chars": {"type": "integer"},
                },
                "required": ["source_name"],
            },
        },
        {
            "name": "get_instrument_profile_schema",
            "description": "Return the expected JSON structure and focus fields for instrument-definition profiles.",
            "inputSchema": {"type": "object", "properties": {}},
        },
        {
            "name": "draft_instrument_profile",
            "description": "Merge vendor sources into a draft instrument-definition JSON, identify missing specifications, and generate follow-up questions for the user.",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "profile_name": {"type": "string"},
                    "sources": {"type": "array", "items": {"type": "string"}},
                    "component_names": {"type": "array", "items": {"type": "string"}},
                    "description": {"type": "string"},
                    "max_chars": {"type": "integer"},
                },
                "required": ["profile_name", "sources"],
            },
        },
        {
            "name": "finalize_instrument_profile",
            "description": "Save and/or apply a finalized instrument-definition JSON or config patch after the user confirms missing specifications.",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "profile_name": {"type": "string"},
                    "profile_json": {"type": "object"},
                    "config_patch": {"type": "object"},
                    "description": {"type": "string"},
                    "metadata": {"type": "object"},
                    "apply_profile": {"type": "boolean"},
                    "save_profile": {"type": "boolean"},
                },
                "required": ["profile_name"],
            },
        },
    ]


def _call_tool(name: str, arguments: Dict[str, Any]):
    service = get_service()
    if name == "get_status":
        return service.get_status()
    if name == "get_config":
        return service.get_config()
    if name == "update_config":
        return service.update_config(arguments.get("config_patch", {}))
    if name == "run_precision":
        return service.run_precision(arguments.get("config_patch", {}))
    if name == "run_optimisation":
        return service.run_optimization(arguments.get("config_patch", {}))
    if name == "simulate_basic":
        return service.simulate_basic(arguments)
    if name == "simulate_advanced":
        return service.simulate_advanced(arguments)
    if name == "get_data_summary":
        return service.get_data_summary()
    if name == "get_results_snapshot":
        return service.get_results_snapshot()
    if name == "get_tau_map":
        return service.get_tau_map()
    if name == "get_phasor_map":
        return service.get_phasor_map(harmonic=int(arguments.get("harmonic", 1)))
    if name == "get_theoretical_locus":
        return service.get_theoretical_locus()
    if name == "get_pixel_analysis":
        return service.get_pixel_analysis(int(arguments["y"]), int(arguments["x"]))
    if name == "get_diagnostics_snapshot":
        return service.get_diagnostics_snapshot(arguments.get("tau_ref"))
    if name == "get_gui_schema":
        return service.get_gui_schema()
    if name == "save_session":
        return service.save_session(str(arguments["session_id"]))
    if name == "load_session":
        return service.load_session(str(arguments["session_id"]))
    if name == "ingest_instrument_profile_source":
        return service.ingest_instrument_profile_source(
            source=str(arguments["source"]),
            profile_name=str(arguments["profile_name"]),
            config_patch=arguments.get("config_patch", {}),
            description=str(arguments.get("description", "")),
            apply_profile=bool(arguments.get("apply_profile", True)),
            save_profile=bool(arguments.get("save_profile", True)),
            max_chars=int(arguments.get("max_chars", 24000)),
        )
    if name == "list_vendor_sources":
        return service.list_vendor_sources()
    if name == "read_vendor_source":
        return service.read_vendor_source(
            source_name=str(arguments["source_name"]),
            max_chars=int(arguments.get("max_chars", 24000)),
        )
    if name == "get_instrument_profile_schema":
        return service.get_instrument_profile_schema()
    if name == "draft_instrument_profile":
        return service.draft_instrument_profile(
            profile_name=str(arguments["profile_name"]),
            sources=list(arguments.get("sources", [])),
            component_names=list(arguments.get("component_names", [])),
            description=str(arguments.get("description", "")),
            max_chars=int(arguments.get("max_chars", 24000)),
        )
    if name == "finalize_instrument_profile":
        return service.finalize_instrument_profile(
            profile_name=str(arguments["profile_name"]),
            profile_json=arguments.get("profile_json"),
            config_patch=arguments.get("config_patch"),
            description=str(arguments.get("description", "")),
            metadata=arguments.get("metadata"),
            apply_profile=bool(arguments.get("apply_profile", True)),
            save_profile=bool(arguments.get("save_profile", True)),
        )
    raise KeyError(f"Unknown tool: {name}")


def _resource_list():
    """Return static resources plus one resource entry per vendor document."""
    resources = [
        {"uri": "hilight://status", "name": "Backend Status", "mimeType": "application/json"},
        {"uri": "hilight://config", "name": "Current Config", "mimeType": "application/json"},
        {"uri": "hilight://gui-schema", "name": "GUI Schema", "mimeType": "application/json"},
        {"uri": "hilight://data-summary", "name": "Data Summary", "mimeType": "application/json"},
        {"uri": "hilight://results", "name": "Results Snapshot", "mimeType": "application/json"},
        {"uri": "hilight://tau-map", "name": "Tau Map", "mimeType": "application/json"},
        {"uri": "hilight://theory-locus", "name": "Theoretical Locus", "mimeType": "application/json"},
        {"uri": "hilight://diagnostics", "name": "Diagnostics Snapshot", "mimeType": "application/json"},
        {"uri": "hilight://instrument-profile-schema", "name": "Instrument Profile Schema", "mimeType": "application/json"},
        {"uri": "hilight://vendors-info/index", "name": "Vendor Info Index", "mimeType": "application/json"},
    ]
    vendors_dir = os.path.join(os.path.dirname(__file__), "..", "docs", "vendors_info")
    if os.path.isdir(vendors_dir):
        for filename in sorted(os.listdir(vendors_dir)):
            path = os.path.join(vendors_dir, filename)
            if os.path.isfile(path):
                resources.append(
                    {
                        "uri": f"hilight://vendors-info/{filename}",
                        "name": f"Vendor Info: {filename}",
                        "mimeType": "application/json",
                    }
                )
    return resources


def _resource_read(uri: str):
    service = get_service()
    if uri == "hilight://status":
        return service.get_status()
    if uri == "hilight://config":
        return service.get_config()
    if uri == "hilight://gui-schema":
        return service.get_gui_schema()
    if uri == "hilight://data-summary":
        return service.get_data_summary()
    if uri == "hilight://results":
        return service.get_results_snapshot()
    if uri == "hilight://tau-map":
        return service.get_tau_map()
    if uri == "hilight://theory-locus":
        return service.get_theoretical_locus()
    if uri == "hilight://diagnostics":
        return service.get_diagnostics_snapshot()
    if uri == "hilight://instrument-profile-schema":
        return service.get_instrument_profile_schema()
    if uri == "hilight://vendors-info/index":
        return service.list_vendor_sources()
    if uri.startswith("hilight://vendors-info/"):
        return service.read_vendor_source(uri.split("hilight://vendors-info/", 1)[1])
    raise KeyError(f"Unknown resource: {uri}")


def handle_request(message: Dict[str, Any]):
    """Dispatch one JSON-RPC request against the MCP surface."""
    method = message.get("method")
    msg_id = message.get("id")
    params = message.get("params", {})

    try:
        if method == "initialize":
            return _success(
                msg_id,
                {
                    "protocolVersion": "2024-11-05",
                    "serverInfo": SERVER_INFO,
                    "capabilities": {
                        "tools": {},
                        "resources": {},
                        "prompts": {},
                    },
                },
            )
        if method == "notifications/initialized":
            return
        if method == "tools/list":
            return _success(msg_id, {"tools": _tool_definitions()})
        if method == "tools/call":
            with contextlib.redirect_stdout(sys.stderr):
                result = _call_tool(params["name"], params.get("arguments", {}))
            return _success(msg_id, {"content": [{"type": "text", "text": json.dumps(result, indent=2)}]})
        if method == "resources/list":
            return _success(msg_id, {"resources": _resource_list()})
        if method == "resources/read":
            with contextlib.redirect_stdout(sys.stderr):
                result = _resource_read(params["uri"])
            return _success(
                msg_id,
                {
                    "contents": [
                        {
                            "uri": params["uri"],
                            "mimeType": "application/json",
                            "text": json.dumps(result, indent=2),
                        }
                    ]
                },
            )
        if method == "prompts/list":
            prompts_map = get_prompts_map()
            prompts = [{"name": item["name"], "description": item["description"]} for item in prompts_map.values()]
            return _success(msg_id, {"prompts": prompts})
        if method == "prompts/get":
            prompts_map = get_prompts_map()
            prompt = prompts_map[params["name"]]
            return _success(
                msg_id,
                {
                    "description": prompt["description"],
                    "messages": [{"role": "user", "content": {"type": "text", "text": prompt["template"]}}],
                },
            )
        return _error(msg_id, -32601, f"Method not found: {method}")
    except Exception as exc:
        return _error(msg_id, -32000, str(exc))


def main():
    while True:
        message = _read_message()
        if message is None:
            break
        handle_request(message)


if __name__ == "__main__":
    main()
