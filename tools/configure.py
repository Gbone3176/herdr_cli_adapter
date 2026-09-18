#!/usr/bin/env python3
"""Install Herdr hook configuration without clobbering user settings.

The adapters are deliberately shell/Python based, but configuration formats
are not interchangeable: Codex uses nested HooksToml tables, Kimi uses hook
array entries, and Claude uses JSON.  This helper keeps those merges in one
place and makes repeated installation idempotent.
"""

import argparse
import json
import os
import re
import shlex
import shutil
import tempfile
import time
from pathlib import Path


CODEX_EVENTS = {
    "SessionStart": "session",
    "UserPromptSubmit": "working",
    "PreToolUse": "working",
    "PostToolUse": "working",
    "Stop": "idle",
}
KIMI_EVENTS = {
    "SessionStart": "session",
    "UserPromptSubmit": "working",
    "PreToolUse": "working",
    "PermissionRequest": "blocked",
    "Stop": "idle",
    "Interrupt": "idle",
}
CLAUDE_EVENTS = {
    "SessionStart": "session",
    "UserPromptSubmit": "working",
    "PreToolUse": "working",
    "Stop": "idle",
}
SIDEBAR_MARKER_START = "# >>> herdr-cli-adapter: sidebar >>>"
SIDEBAR_MARKER_END = "# <<< herdr-cli-adapter: sidebar <<<"
CODEX_MARKER_START = "# >>> herdr-cli-adapter: codex >>>"
CODEX_MARKER_END = "# <<< herdr-cli-adapter: codex <<<"
KIMI_MARKER_START = "# >>> herdr-cli-adapter: kimi >>>"
KIMI_MARKER_END = "# <<< herdr-cli-adapter: kimi <<<"


class ConfigurationError(RuntimeError):
    pass


def shell_command(script_path, action):
    return "bash %s %s" % (shlex.quote(str(script_path)), action)


def toml_string(value):
    return json.dumps(value, ensure_ascii=False)


def read_text(path):
    try:
        return path.read_text(encoding="utf-8")
    except FileNotFoundError:
        return ""


def backup_path(path):
    stamp = time.strftime("%Y%m%d%H%M%S", time.gmtime())
    candidate = path.with_name(path.name + ".bak." + stamp)
    suffix = 0
    while candidate.exists():
        suffix += 1
        candidate = path.with_name(path.name + ".bak.%s.%s" % (stamp, suffix))
    return candidate


def atomic_write(path, content):
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists() and path.read_text(encoding="utf-8") == content:
        return None
    backup = None
    if path.exists():
        backup = backup_path(path)
        shutil.copy2(path, backup)
    mode = path.stat().st_mode & 0o777 if path.exists() else 0o600
    fd, temporary = tempfile.mkstemp(prefix=".%s." % path.name, dir=str(path.parent))
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as stream:
            stream.write(content)
        os.chmod(temporary, mode)
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)
    return backup


def replace_marked_block(text, start, end, replacement):
    begin = text.find(start)
    if begin < 0:
        return None
    finish = text.find(end, begin)
    if finish < 0:
        raise ConfigurationError("found an incomplete configuration marker: %s" % start)
    finish += len(end)
    before = text[:begin].rstrip("\n")
    after = text[finish:].lstrip("\n")
    pieces = [before, replacement.rstrip("\n"), after]
    return "\n\n".join(piece for piece in pieces if piece) + "\n"


def codex_block(script_path, include_hooks_header):
    lines = [CODEX_MARKER_START]
    if include_hooks_header:
        lines.append("[hooks]")
    for event, action in CODEX_EVENTS.items():
        lines.extend(
            [
                "[[hooks.%s]]" % event,
                "[[hooks.%s.hooks]]" % event,
                'type = "command"',
                "command = %s" % toml_string(shell_command(script_path, action)),
                "",
            ]
        )
    lines.append(CODEX_MARKER_END)
    return "\n".join(lines)


def strip_legacy_codex_entries(text):
    """Remove the repository's pre-HooksToml ``[[hooks]]`` entries."""

    lines = text.splitlines(True)
    kept = []
    index = 0
    table_start = re.compile(r"^\s*\[\[?[^]]+\]\]?\s*$")
    while index < len(lines):
        if lines[index].strip() != "[[hooks]]":
            kept.append(lines[index])
            index += 1
            continue
        end = index + 1
        while end < len(lines) and not table_start.match(lines[end]):
            end += 1
        block = "".join(lines[index:end])
        if "event =" in block and "herdr-agent-state.sh" in block:
            index = end
            continue
        kept.extend(lines[index:end])
        index = end
    return "".join(kept)


def rewrite_modern_codex_commands(text, script_path):
    lines = text.splitlines(True)
    current_event = None
    output = []
    for line in lines:
        match = re.match(r"^\s*\[\[hooks\.([A-Za-z]+)\]\]\s*$", line)
        if match:
            current_event = match.group(1)
        if line.startswith("[hooks.state]") or line.startswith("[hooks.state."):
            current_event = None
        if current_event in CODEX_EVENTS and "herdr-agent-state.sh" in line and line.lstrip().startswith("command"):
            line = "command = %s\n" % toml_string(
                shell_command(script_path, CODEX_EVENTS[current_event])
            )
        output.append(line)
    return "".join(output)


def has_modern_codex_hooks(text):
    for event, action in CODEX_EVENTS.items():
        pattern = (
            r"(?ms)^\[\[hooks\.%s\]\].*?"
            r"^\[\[hooks\.%s\.hooks\]\].*?"
            r"^\s*type\s*=\s*['\"]command['\"].*?"
            r"^\s*command\s*=.*herdr-agent-state\.sh\s+%s['\"]?\s*$"
        ) % (re.escape(event), re.escape(event), re.escape(action))
        if not re.search(pattern, text):
            return False
    return True


def merge_codex(path, script_path):
    original = read_text(path)
    marker_body = ""
    marker_begin = original.find(CODEX_MARKER_START)
    if marker_begin >= 0:
        marker_end = original.find(CODEX_MARKER_END, marker_begin)
        if marker_end < 0:
            raise ConfigurationError("found an incomplete Codex configuration marker")
        marker_body = original[marker_begin : marker_end + len(CODEX_MARKER_END)]
    marked = replace_marked_block(
        original,
        CODEX_MARKER_START,
        CODEX_MARKER_END,
        codex_block(script_path, bool(re.search(r"(?m)^\[hooks\]\s*$", marker_body))),
    )
    if marked is not None:
        return marked

    text = strip_legacy_codex_entries(original)
    text = rewrite_modern_codex_commands(text, script_path)
    if has_modern_codex_hooks(text):
        return text

    include_header = not re.search(r"(?m)^\[hooks\]\s*$", text)
    block = codex_block(script_path, include_header)
    insertion = text.find("[hooks.state]")
    if insertion < 0:
        separator = "\n\n" if text.strip() else ""
        return text.rstrip("\n") + separator + block + "\n"
    before = text[:insertion].rstrip("\n")
    after = text[insertion:].lstrip("\n")
    return before + "\n\n" + block + "\n\n" + after


def kimi_block(script_path):
    lines = [KIMI_MARKER_START]
    for event, action in KIMI_EVENTS.items():
        lines.extend(
            [
                "[[hooks]]",
                'event = "%s"' % event,
                "command = %s" % toml_string(shell_command(script_path, action)),
                "",
            ]
        )
    lines.append(KIMI_MARKER_END)
    return "\n".join(lines)


def rewrite_kimi_commands(text, script_path):
    lines = text.splitlines(True)
    current_event = None
    output = []
    for line in lines:
        match = re.match(r'^\s*event\s*=\s*["\']([^"\']+)["\']', line)
        if match:
            current_event = match.group(1)
        if current_event in KIMI_EVENTS and "herdr-agent-state.sh" in line and line.lstrip().startswith("command"):
            line = "command = %s\n" % toml_string(
                shell_command(script_path, KIMI_EVENTS[current_event])
            )
        output.append(line)
    return "".join(output)


def has_kimi_hooks(text):
    return all(
        re.search(
            r"(?ms)^\s*event\s*=\s*[\"']%s[\"'].*?herdr-agent-state\.sh\s+%s[\"']?\s*$"
            % (event, action),
            text,
        )
        for event, action in KIMI_EVENTS.items()
    )


def merge_kimi(path, script_path):
    original = read_text(path)
    marked = replace_marked_block(original, KIMI_MARKER_START, KIMI_MARKER_END, kimi_block(script_path))
    if marked is not None:
        return marked
    text = rewrite_kimi_commands(original, script_path)
    if has_kimi_hooks(text):
        return text
    separator = "\n\n" if text.strip() else ""
    return text.rstrip("\n") + separator + kimi_block(script_path) + "\n"


def claude_entries(script_path):
    result = {}
    for event, action in CLAUDE_EVENTS.items():
        result[event] = {
            "hooks": [
                {
                    "type": "command",
                    "command": shell_command(script_path, action),
                }
            ]
        }
    return result


def is_herdr_command(command, action):
    return isinstance(command, str) and re.search(
        r"herdr-agent-state\.sh[\"']?\s+%s\s*$" % re.escape(action), command
    ) is not None


def merge_claude(path, script_path):
    if path.exists():
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            raise ConfigurationError("invalid Claude settings JSON: %s" % exc)
    else:
        data = {}
    if not isinstance(data, dict):
        raise ConfigurationError("Claude settings must be a JSON object")
    hooks = data.setdefault("hooks", {})
    if not isinstance(hooks, dict):
        raise ConfigurationError("Claude settings 'hooks' must be an object")
    for event, entry in claude_entries(script_path).items():
        groups = hooks.setdefault(event, [])
        if not isinstance(groups, list):
            raise ConfigurationError("Claude hook %s must be an array" % event)
        command = entry["hooks"][0]["command"]
        found = False
        for group in groups:
            if not isinstance(group, dict):
                continue
            for item in group.get("hooks", []):
                if not isinstance(item, dict) or item.get("type") != "command":
                    continue
                if item.get("command") == command or is_herdr_command(item.get("command"), CLAUDE_EVENTS[event]):
                    item["command"] = command
                    found = True
                    break
            if found:
                break
        if not found:
            groups.append(entry)
    return json.dumps(data, ensure_ascii=False, indent=2) + "\n"


def merge_sidebar(path):
    original = read_text(path)
    block = "\n".join(
        [
            SIDEBAR_MARKER_START,
            "[ui.sidebar.agents]",
            'rows = [["state_icon", "workspace", "tab"], ["agent"], ["$task", "$model"]]',
            SIDEBAR_MARKER_END,
        ]
    )
    marked = replace_marked_block(original, SIDEBAR_MARKER_START, SIDEBAR_MARKER_END, block)
    if marked is not None:
        return marked

    section = re.search(r"(?m)^\[ui\.sidebar\.agents\]\s*$", original)
    if section:
        end = re.search(r"(?m)^\[[^\n]+\]\s*$", original[section.end():])
        section_text = original[section.end() : section.end() + (end.start() if end else len(original))]
        if re.search(r"(?m)^rows\s*=", section_text):
            return original
        return original[: section.end()] + '\nrows = [["state_icon", "workspace", "tab"], ["agent"], ["$task", "$model"]]\n' + original[section.end() :]
    return original.rstrip("\n") + ("\n\n" if original else "") + block + "\n"


def configure(kind, config_path, script_path, herdr_config):
    if kind == "codex":
        content = merge_codex(config_path, script_path)
    elif kind == "kimi":
        content = merge_kimi(config_path, script_path)
    elif kind == "claude":
        content = merge_claude(config_path, script_path)
    else:
        raise ConfigurationError("unsupported adapter: %s" % kind)
    changed = atomic_write(config_path, content)
    sidebar_changed = atomic_write(herdr_config, merge_sidebar(herdr_config))
    return changed, sidebar_changed


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("adapter", choices=("codex", "kimi", "claude"))
    parser.add_argument("--config", required=True, type=Path)
    parser.add_argument("--script", required=True, type=Path)
    parser.add_argument("--herdr-config", required=True, type=Path)
    args = parser.parse_args()
    try:
        changed, sidebar_changed = configure(
            args.adapter, args.config, args.script, args.herdr_config
        )
    except ConfigurationError as exc:
        parser.error(str(exc))
    print("Configured %s: %s" % (args.adapter, args.config))
    if changed:
        print("  backup: %s" % changed)
    if sidebar_changed:
        print("  Herdr sidebar backup: %s" % sidebar_changed)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
