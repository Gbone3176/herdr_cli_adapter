#!/usr/bin/env python3
"""Dependency-free behavior tests for the Herdr reporter."""

import importlib.util
import io
import json
import os
import socket
import sys
import tempfile
import threading
import uuid
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
REPORTER_PATH = ROOT / "adapters" / "python" / "herdr_report.py"
SPEC = importlib.util.spec_from_file_location("herdr_report_test", REPORTER_PATH)
REPORTER = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(REPORTER)


def invoke(action, payload, label="codex", capture_metadata=False, pane_id=None):
    pane_id = pane_id or ("test-" + uuid.uuid4().hex)
    with tempfile.TemporaryDirectory(prefix="herdr-reporter-test-") as directory:
        socket_path = os.path.join(directory, "herdr.sock")
        server = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        server.bind(socket_path)
        server.listen(1)
        received = []
        metadata_calls = []

        def serve():
            connection, _ = server.accept()
            with connection:
                data = b""
                while b"\n" not in data:
                    data += connection.recv(4096)
                received.append(json.loads(data.splitlines()[0]))
                connection.sendall(b"{}\n")

        thread = threading.Thread(target=serve)
        thread.start()
        old_env = os.environ.copy()
        old_argv = sys.argv[:]
        old_stdin = sys.stdin
        old_run = REPORTER.subprocess.run
        try:
            os.environ.update(
                {
                    "HERDR_ENV": "1",
                    "HERDR_SOCKET_PATH": socket_path,
                    "HERDR_PANE_ID": pane_id,
                    "HERDR_AGENT_LABEL": label,
                }
            )
            sys.argv = [str(REPORTER_PATH), action]
            sys.stdin = io.StringIO(json.dumps(payload))
            if capture_metadata:
                REPORTER.subprocess.run = lambda args, **kwargs: metadata_calls.append(args)
            REPORTER.main()
        finally:
            os.environ.clear()
            os.environ.update(old_env)
            sys.argv = old_argv
            sys.stdin = old_stdin
            REPORTER.subprocess.run = old_run
        thread.join(timeout=2)
        server.close()
        assert received, "reporter did not send an event"
        return received[0], metadata_calls


def test_model_metadata():
    event, calls = invoke(
        "working",
        {"session_id": "session-1", "prompt": "show metadata", "model": "gpt-test"},
        capture_metadata=True,
    )
    assert event["params"]["state"] == "working"
    assert calls and "model=gpt-test" in calls[0]


def test_goal_keeps_codex_working():
    pane_id = "test-goal-" + uuid.uuid4().hex
    started, _ = invoke("working", {"tool_name": "create_goal"}, pane_id=pane_id)
    continued, _ = invoke("idle", {}, pane_id=pane_id)
    completed, _ = invoke("working", {"status": "complete"}, pane_id=pane_id)
    assert started["params"]["state"] == "working"
    assert continued["params"]["state"] == "working"
    assert completed["params"]["state"] == "idle"


def test_missing_pane_is_fail_closed():
    old_env = os.environ.copy()
    old_argv = sys.argv[:]
    old_stdin = sys.stdin
    try:
        os.environ.update({"HERDR_ENV": "1", "HERDR_SOCKET_PATH": "/missing"})
        os.environ.pop("HERDR_PANE_ID", None)
        sys.argv = [str(REPORTER_PATH), "working"]
        sys.stdin = io.StringIO("{}")
        REPORTER.main()
    finally:
        os.environ.clear()
        os.environ.update(old_env)
        sys.argv = old_argv
        sys.stdin = old_stdin


if __name__ == "__main__":
    test_model_metadata()
    test_goal_keeps_codex_working()
    test_missing_pane_is_fail_closed()
    print("reporter behavior: ok")
