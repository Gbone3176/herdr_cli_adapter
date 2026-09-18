#!/usr/bin/env python3
"""Translate CLI hook events into Herdr agent state and sidebar metadata."""

import json
import os
import socket
import subprocess
import sys
import tempfile
import time


MAX_TITLE_LENGTH = 120
SOCKET_TIMEOUT_SECONDS = 0.5


def send(method, params):
    request = json.dumps({"id": f"herdr:{params['agent']}:{time.time_ns()}", "method": method, "params": params})
    with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as client:
        client.settimeout(SOCKET_TIMEOUT_SECONDS)
        client.connect(os.environ["HERDR_SOCKET_PATH"])
        client.sendall((request + "\n").encode())
        client.recv(4096)


def first_prompt(payload):
    if not isinstance(payload, dict):
        return None
    for key in ("prompt", "user_prompt", "input", "text"):
        value = payload.get(key)
        if isinstance(value, str) and value.strip():
            line = " ".join(value.strip().splitlines()[0].split())
            return "".join(char for char in line if ord(char) >= 0x20 and char != "\x7f")[:MAX_TITLE_LENGTH]
    return None


def model_name(payload):
    if isinstance(payload, dict):
        value = payload.get("model")
        if isinstance(value, str) and value.strip():
            return value.strip()[:MAX_TITLE_LENGTH]
    return os.environ.get("HERDR_AGENT_MODEL", "").strip()[:MAX_TITLE_LENGTH]


def walk_values(value):
    if isinstance(value, dict):
        for key, child in value.items():
            yield str(key).lower(), child
            yield from walk_values(child)
    elif isinstance(value, list):
        for child in value:
            yield from walk_values(child)


def goal_signal(payload):
    """Return (active, terminal) when a hook payload describes Codex Goal."""
    if not isinstance(payload, (dict, list)):
        return False, False
    active = terminal = False
    for key, value in walk_values(payload):
        text = str(value).strip().lower() if isinstance(value, (str, int, float)) else ""
        if key in {"tool", "tool_name", "name", "command", "event", "mode"}:
            if "goal" in text or text in {"create_goal", "update_goal", "get_goal"}:
                active = True
        if key in {"status", "goal_status", "state"}:
            if text in {"complete", "completed", "cancelled", "canceled", "failed", "blocked"}:
                terminal = True
            elif text in {"active", "working", "pending", "in_progress", "in-progress"}:
                active = True
    prompt = first_prompt(payload)
    if prompt:
        lowered = prompt.lower()
        if lowered.startswith("/goal") or "goal mode" in lowered:
            active = True
            if any(word in lowered for word in ("clear", "complete", "cancel", "stop")):
                terminal = True
    return active, terminal


def goal_state_path(pane_id):
    safe_pane = "".join(char if char.isalnum() or char in "._-" else "_" for char in pane_id)
    return os.path.join(tempfile.gettempdir(), f"herdr-codex-goal-{safe_pane[:80]}.state")


def goal_is_active(pane_id):
    path = goal_state_path(pane_id)
    try:
        timestamp = float(open(path, encoding="utf-8").read().strip())
    except (OSError, ValueError):
        return False
    if time.time() - timestamp > 86400:
        try:
            os.unlink(path)
        except OSError:
            pass
        return False
    return True


def set_goal_active(pane_id, active):
    path = goal_state_path(pane_id)
    if active:
        try:
            with open(path, "w", encoding="utf-8") as state:
                state.write(str(time.time()))
        except OSError:
            pass
    else:
        try:
            os.unlink(path)
        except FileNotFoundError:
            pass
        except OSError:
            pass


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
    pane_id = os.environ.get("HERDR_PANE_ID")
    if not pane_id:
        return
    goal_active, goal_terminal = goal_signal(payload)
    if label == "codex":
        if goal_terminal:
            set_goal_active(pane_id, False)
            action = "idle"
        elif goal_active:
            set_goal_active(pane_id, True)
        elif action == "idle" and goal_is_active(pane_id):
            action = "working"
    session_id = payload.get("session_id") if isinstance(payload, dict) else None
    params = {
        "pane_id": pane_id,
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
        if title and os.environ.get("HERDR_METADATA", "1") != "0":
            metadata = [
                os.environ.get("HERDR_BIN", "herdr"), "pane", "report-metadata", pane_id,
                "--source", f"herdr:{label}", "--title", title,
                "--token", f"task={title}",
            ]
            model = model_name(payload)
            if model:
                metadata.extend(("--token", f"model={model}"))
            subprocess.run(
                metadata,
                check=False,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                timeout=1,
            )
    except (OSError, subprocess.TimeoutExpired):
        return


if __name__ == "__main__":
    main()
