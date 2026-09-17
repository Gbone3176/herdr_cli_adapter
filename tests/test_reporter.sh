#!/bin/sh
set -eu
script=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)/adapters/generic/herdr-report.sh
HERDR_ENV=0 "$script" idle </dev/null
python3 - <<'PY'
import json
import os
import socket
import subprocess
import tempfile
import threading

root = os.getcwd()
reporter = os.path.join(root, "adapters", "codex", "herdr-agent-state.sh")
socket_path = os.path.join(tempfile.mkdtemp(), "herdr.sock")
server = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
server.bind(socket_path)
server.listen(4)
messages = []

def receive():
    while len(messages) < 3:
        conn, _ = server.accept()
        messages.append(json.loads(conn.recv(4096).decode()))
        conn.sendall(b'{"ok":true}\n')
        conn.close()

thread = threading.Thread(target=receive, daemon=True)
thread.start()
env = os.environ.copy()
env.update({"HERDR_ENV": "1", "HERDR_SOCKET_PATH": socket_path, "HERDR_PANE_ID": "test-goal", "HERDR_AGENT_LABEL": "codex"})
def invoke(action, payload):
    subprocess.run([reporter, action], input=json.dumps(payload).encode(), env=env, check=True)

invoke("working", {"tool_name": "create_goal", "status": "active"})
invoke("idle", {})
invoke("working", {"tool_name": "update_goal", "status": "complete"})
thread.join(2)
states = [message["params"].get("state") for message in messages]
assert states == ["working", "working", "idle"], states
print("goal state regression test passed")
PY
printf '%s\n' 'reporter smoke test passed'
