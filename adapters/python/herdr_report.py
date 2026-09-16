#!/usr/bin/env python3
"""Translate CLI hook events into Herdr agent state and sidebar metadata."""

import json
import os
import socket
import subprocess
import sys
import time


def send(method, params):
    request = json.dumps({"id": f"herdr:{params['agent']}:{time.time_ns()}", "method": method, "params": params})
    with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as client:
        client.settimeout(0.5)
        client.connect(os.environ["HERDR_SOCKET_PATH"])
        client.sendall((request + "\n").encode())
        client.recv(4096)


def first_prompt(payload):
    if not isinstance(payload, dict):
        return None
    for key in ("prompt", "user_prompt", "input", "text"):
        value = payload.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip().splitlines()[0][:120]
    return None


def main():
    action = sys.argv[1] if len(sys.argv) > 1 else ""
    if action == "session_start":
        action = "session"
    if action not in {"session", "working", "blocked", "idle"}:
        return
    if os.environ.get("HERDR_ENV") != "1" or not os.environ.get("HERDR_SOCKET_PATH"):
        return
    try:
        payload = json.load(sys.stdin)
    except Exception:
        payload = {}
    label = os.environ.get("HERDR_AGENT_LABEL", "generic")
    session_id = payload.get("session_id") if isinstance(payload, dict) else None
    params = {
        "pane_id": os.environ["HERDR_PANE_ID"],
        "source": f"herdr:{label}",
        "agent": label,
        "seq": time.time_ns(),
    }
    if action == "session":
        if not session_id:
            return
        method = "pane.report_agent_session"
        params["session_start_source"] = "startup"
    else:
        method = "pane.report_agent"
        params["state"] = action
    if session_id:
        params["agent_session_id"] = session_id
    try:
        send(method, params)
        title = first_prompt(payload) if action == "working" else None
        if title:
            subprocess.run(
                [
                    "herdr", "pane", "report-metadata", os.environ["HERDR_PANE_ID"],
                    "--source", f"herdr:{label}", "--title", title,
                    "--token", f"task={title}",
                    "--token", f"model={os.environ.get('HERDR_AGENT_MODEL', '')}",
                ], check=False, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
            )
    except OSError:
        return


if __name__ == "__main__":
    main()
