import json
import os
from pathlib import Path
import subprocess
import sys

import pytest


INSTALLER = Path(__file__).with_name("install.sh")


@pytest.fixture
def install(tmp_path):
    home = tmp_path / "home"
    ai = home / ".dotfiles/ai"
    ai.mkdir(parents=True)
    source = tmp_path / "source"
    skills = {
        name: {
            "sourceUrl": "https://github.com/example/skills.git",
            "skillPath": f"skills/{name}/SKILL.md",
        }
        for name in ("first", "second")
    }
    (ai / "skill-lock.json").write_text(json.dumps({"skills": skills}))
    for name, entry in skills.items():
        path = source / entry["skillPath"]
        path.parent.mkdir(parents=True)
        path.write_text(f"{name} skill")
    (home / ".agent-browser/browsers/chromium").mkdir(parents=True)
    commands = tmp_path / "commands.jsonl"
    bins = tmp_path / "bin"
    bins.mkdir()
    stub = f"""#!{sys.executable}
import json, os, shutil, sys
from pathlib import Path
command = Path(sys.argv[0]).name
with open(os.environ['COMMAND_LOG'], 'a') as log:
    log.write(json.dumps([command, *sys.argv[1:]]) + '\\n')
if command == 'git':
    shutil.copytree(os.environ['SKILL_SOURCE'], sys.argv[-1])
if command == 'npx':
    sys.exit(int(os.environ['UPDATE_EXIT_CODE']))
"""
    for command in ("git", "npx", "agent-browser"):
        path = bins / command
        path.write_text(stub)
        path.chmod(0o755)

    def run(installed=("first", "second"), update_exit_code=0):
        for name in installed:
            path = home / ".agents/skills" / name
            path.mkdir(parents=True)
            (path / "SKILL.md").write_text(f"{name} skill")
        result = subprocess.run(
            ["/bin/sh", str(INSTALLER)],
            env=dict(
                os.environ,
                HOME=str(home),
                PATH=f"{bins}:{os.environ['PATH']}",
                COMMAND_LOG=str(commands),
                SKILL_SOURCE=str(source),
                UPDATE_EXIT_CODE=str(update_exit_code),
            ),
            capture_output=True,
            text=True,
            timeout=10,
        )
        assert result.returncode == 0, result.stdout + result.stderr
        calls = [json.loads(line) for line in commands.read_text().splitlines()]
        return home, calls, result.stdout

    return run


@pytest.mark.parametrize(
    "installed, expected_clones",
    [(("first", "second"), 0), (("first",), 1), ((), 1)],
)
@pytest.mark.parametrize("update_exit_code", [0, 1])
def test_sync_only_clones_to_restore_missing_skills(
    install, installed, expected_clones, update_exit_code
):
    home, calls, output = install(installed, update_exit_code)

    assert sum(call[0] == "git" for call in calls) == expected_clones
    assert [call for call in calls if call[0] == "npx"] == [
        ["npx", "-y", "skills@latest", "update", "-g", "-y"]
    ]
    for name in ("first", "second"):
        skill = home / ".claude/skills" / name
        assert skill.is_symlink()
        assert (skill / "SKILL.md").read_text() == f"{name} skill"
    if update_exit_code:
        assert "skill update failed" in output
