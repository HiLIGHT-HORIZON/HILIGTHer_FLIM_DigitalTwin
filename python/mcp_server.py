import json
import os
import sys
import contextlib
from typing import Any, Dict

sys.path.insert(0, os.path.dirname(__file__))

from backend.service_api import DigitalTwinService
from mcp_prompts import get_prompts


SERVICE = DigitalTwinService()
PROMPTS = get_prompts()
SERVER_INFO = {"name": "hilighter-digital-twin-mcp", "version": "1.0.0"}


def _read_message():
    headers = {}
    while True:
        line = sys.stdin.buffer.readline()
        if not line:
            return None
        line = line.decode("utf-8").strip()
        if not line:
            break
        key, value = line.split(":", 1)
        headers[key.strip().lower()] = value.strip()
    length = int(headers.get("content-length", "0"))
    if length <= 0:
        return None
    payload = sys.stdin.buffer.read(length)
    return json.loads(payload.decode("utf-8"))


def _write_message(message: Dict[str, Any]):
    payload = json.dumps(message).encode("utf-8")
    header = f"Content-Length: {len(payload)}\r\n\r\n".encode("utf-8")
    sys.stdout.buffer.write(header)
    sys.stdout.buffer.write(payload)
    sys.stdout.buffer.flush()


def _success(msg_id, result):
    _write_message({"jsonrpc": "2.0", "id": msg_id, "result": result})


def _error(msg_id, code, message):
    _write_message({"jsonrpc": "2.0", "id": msg_id, "error": {"code": code, "message": message}})


def _tool_definitions():
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
    ]


def _call_tool(name: str, arguments: Dict[str, Any]):
    if name == "get_status":
        return SERVICE.get_status()
    if name == "get_config":
        return SERVICE.get_config()
    if name == "update_config":
        return SERVICE.update_config(arguments.get("config_patch", {}))
    if name == "run_precision":
        return SERVICE.run_precision(arguments.get("config_patch", {}))
    if name == "simulate_basic":
        return SERVICE.simulate_basic(arguments)
    if name == "simulate_advanced":
        return SERVICE.simulate_advanced(arguments)
    if name == "get_data_summary":
        return SERVICE.get_data_summary()
    if name == "get_diagnostics_snapshot":
        return SERVICE.get_diagnostics_snapshot(arguments.get("tau_ref"))
    if name == "get_gui_schema":
        return SERVICE.get_gui_schema()
    raise KeyError(f"Unknown tool: {name}")


def _resource_list():
    return [
        {"uri": "hilight://status", "name": "Backend Status", "mimeType": "application/json"},
        {"uri": "hilight://config", "name": "Current Config", "mimeType": "application/json"},
        {"uri": "hilight://gui-schema", "name": "GUI Schema", "mimeType": "application/json"},
    ]


def _resource_read(uri: str):
    if uri == "hilight://status":
        return SERVICE.get_status()
    if uri == "hilight://config":
        return SERVICE.get_config()
    if uri == "hilight://gui-schema":
        return SERVICE.get_gui_schema()
    raise KeyError(f"Unknown resource: {uri}")


def handle_request(message: Dict[str, Any]):
    method = message.get("method")
    msg_id = message.get("id")
    params = message.get("params", {})

    try:
        if method == "initialize":
            return _success(msg_id, {
                "protocolVersion": "2024-11-05",
                "serverInfo": SERVER_INFO,
                "capabilities": {
                    "tools": {},
                    "resources": {},
                    "prompts": {},
                },
            })
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
            return _success(msg_id, {"contents": [{"uri": params["uri"], "mimeType": "application/json", "text": json.dumps(result, indent=2)}]})
        if method == "prompts/list":
            prompts = [{"name": item["name"], "description": item["description"]} for item in PROMPTS.values()]
            return _success(msg_id, {"prompts": prompts})
        if method == "prompts/get":
            prompt = PROMPTS[params["name"]]
            return _success(msg_id, {
                "description": prompt["description"],
                "messages": [{"role": "user", "content": {"type": "text", "text": prompt["template"]}}],
            })
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
