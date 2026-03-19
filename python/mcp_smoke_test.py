import json
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
SERVER = ROOT / "python" / "mcp_server.py"


def _send(proc, payload):
    body = json.dumps(payload).encode("utf-8")
    header = f"Content-Length: {len(body)}\r\n\r\n".encode("utf-8")
    proc.stdin.write(header)
    proc.stdin.write(body)
    proc.stdin.flush()


def _recv(proc):
    headers = {}
    while True:
        line = proc.stdout.readline()
        if not line:
            raise RuntimeError("MCP server closed stdout unexpectedly.")
        line = line.decode("utf-8").strip()
        if not line:
            break
        key, value = line.split(":", 1)
        headers[key.strip().lower()] = value.strip()
    length = int(headers.get("content-length", "0"))
    if length <= 0:
        raise RuntimeError("Received MCP message without Content-Length.")
    payload = proc.stdout.read(length)
    return json.loads(payload.decode("utf-8"))


def _request(proc, msg_id, method, params=None):
    _send(proc, {"jsonrpc": "2.0", "id": msg_id, "method": method, "params": params or {}})
    response = _recv(proc)
    if "error" in response:
        raise RuntimeError(f"{method} failed: {response['error']}")
    return response["result"]


def main():
    proc = subprocess.Popen(
        [sys.executable, str(SERVER)],
        cwd=str(ROOT),
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )

    try:
        initialize = _request(
            proc,
            1,
            "initialize",
            {
                "protocolVersion": "2024-11-05",
                "clientInfo": {"name": "hilight-mcp-smoke-test", "version": "1.0.0"},
                "capabilities": {},
            },
        )
        _send(proc, {"jsonrpc": "2.0", "method": "notifications/initialized", "params": {}})

        tools = _request(proc, 2, "tools/list")["tools"]
        resources = _request(proc, 3, "resources/list")["resources"]
        prompts = _request(proc, 4, "prompts/list")["prompts"]

        status_call = _request(proc, 5, "tools/call", {"name": "get_status", "arguments": {}})
        precision_call = _request(
            proc,
            6,
            "tools/call",
            {
                "name": "run_precision",
                "arguments": {
                    "config_patch": {
                        "f_x_steps": 8,
                        "precision_validate_mc": False,
                        "precision_photons": 300,
                    }
                },
            },
        )
        config_resource = _request(proc, 7, "resources/read", {"uri": "hilight://config"})
        prompt_payload = _request(proc, 8, "prompts/get", {"name": "precision-audit"})

        tool_names = sorted(item["name"] for item in tools)
        resource_names = sorted(item["uri"] for item in resources)
        prompt_names = sorted(item["name"] for item in prompts)
        required_tools = {
            "get_status",
            "get_config",
            "run_precision",
            "run_optimisation",
            "get_results_snapshot",
            "get_tau_map",
            "get_phasor_map",
            "get_pixel_analysis",
            "get_gui_schema",
        }
        required_resources = {
            "hilight://status",
            "hilight://config",
            "hilight://gui-schema",
            "hilight://results",
            "hilight://diagnostics",
        }
        required_prompts = {
            "precision-audit",
            "instrument-design",
            "data-inspection",
            "workspace-navigation",
            "optimisation-loop",
        }
        missing_tools = sorted(required_tools.difference(tool_names))
        missing_resources = sorted(required_resources.difference(resource_names))
        missing_prompts = sorted(required_prompts.difference(prompt_names))

        summary = {
            "server": initialize["serverInfo"],
            "tool_count": len(tool_names),
            "resource_count": len(resource_names),
            "prompt_count": len(prompt_names),
            "missing_tools": missing_tools,
            "missing_resources": missing_resources,
            "missing_prompts": missing_prompts,
            "status_call_ok": "content" in status_call and bool(status_call["content"]),
            "precision_call_ok": "content" in precision_call and bool(precision_call["content"]),
            "config_resource_ok": bool(config_resource.get("contents")),
            "prompt_get_ok": bool(prompt_payload.get("messages")),
        }

        if (
            missing_tools
            or missing_resources
            or missing_prompts
            or not summary["status_call_ok"]
            or not summary["precision_call_ok"]
            or not summary["config_resource_ok"]
            or not summary["prompt_get_ok"]
        ):
            print(json.dumps(summary, indent=2))
            raise SystemExit(1)

        print(json.dumps(summary, indent=2))
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=3)
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.wait(timeout=3)


if __name__ == "__main__":
    main()
