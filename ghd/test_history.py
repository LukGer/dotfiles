import importlib.util
import json
from pathlib import Path

import pytest


spec = importlib.util.spec_from_file_location("history", Path(__file__).with_name("history.py"))
history = importlib.util.module_from_spec(spec)
spec.loader.exec_module(history)


@pytest.mark.parametrize("picked", [None, 0, 1])
def test_history_opens_the_selected_review_with_a_copyable_preview(tmp_path, monkeypatch, picked):
    for name in ("older", "newer"):
        (tmp_path / f"{name}.md").write_text(f"# {name}")
        (tmp_path / f"{name}.json").write_text(json.dumps({
            "repo": "owner/repo", "pr": 42, "at": name, "tool": "codex", "sha": "abc",
        }))
    monkeypatch.setattr(history, "STORE", str(tmp_path))
    monkeypatch.setattr(history, "current", lambda key: ("OPEN", "abc"))
    requests, opened = [], []

    def choose(title, items, **options):
        requests.append((title, items, options))
        return picked

    monkeypatch.setattr(history, "choose", choose)
    monkeypatch.setattr(history.os, "execv", lambda *args: opened.append(args))
    history.main(["owner/repo", "42"])
    assert requests[0][2] == {"copy": True}
    items = requests[0][1]
    assert all("up to date" in item["label"] for item in items)
    assert {Path(item["preview_file"]).name for item in items} == {"older.md", "newer.md"}
    assert opened == ([(f"{history.LIB}/view", [f"{history.LIB}/view", "owner/repo", "42", items[picked]["preview_file"]])] if picked is not None else [])
