#!/usr/bin/env python3
import argparse
import json
from pathlib import Path
import subprocess
import sys
import tempfile

from ui import pause


LIB = Path(__file__).resolve().parent


def main():
    parser = argparse.ArgumentParser(prog="ghd chat", description="Chat about a PR's diff without a checkout.")
    parser.add_argument("repo", help="owner/repo")
    parser.add_argument("pr", type=int)
    parser.add_argument("--model", help="OpenCode provider/model#variant; otherwise choose interactively")
    args = parser.parse_args()
    with tempfile.TemporaryDirectory(prefix="ghd-chat-") as directory:
        directory = Path(directory)
        model = args.model
        if not model:
            selection = directory / "selection.json"
            subprocess.run([str(LIB / "tui"), "menu", str(selection), "chat"], check=True)
            if not selection.exists():
                return 0
            model = json.loads(selection.read_text())["model"]

        print(f"Loading {args.repo}#{args.pr} from GitHub…", flush=True)
        view = json.loads(subprocess.run([
            "gh", "pr", "view", str(args.pr), "--repo", args.repo,
            "--json", "title,body,url,headRefName,baseRefName,headRefOid",
        ], capture_output=True, text=True, check=True).stdout)
        diff = subprocess.run([
            "gh", "pr", "diff", str(args.pr), "--repo", args.repo, "--color", "never",
        ], capture_output=True, text=True, check=True).stdout
        context = directory / "pr.md"
        context.write_text(
            f"# {args.repo}#{args.pr}: {view['title']}\n\n{view['url']}\n"
            f"Branch: {view['headRefName']} → {view['baseRefName']}\n"
            f"Head when loaded: {view['headRefOid']}\n\n"
            f"## Description\n\n{view['body'] or '(empty)'}\n\n"
            f"## Diff\n\n```diff\n{diff.rstrip()}\n```\n"
        )
        (directory / "opencode.json").write_text(json.dumps({
            "default_agent": "ghd-chat",
            "model": model,
            "instructions": [context.name],
        }))
        command = [
            "opencode", "--standalone",
            "--prompt", "Give me a brief overview of this PR, then help me understand it as I ask questions.",
        ]
        return subprocess.call(command, cwd=directory)


if __name__ == "__main__":
    try:
        code = main()
        if code:
            pause(f"PR chat exited with status {code}.")
        sys.exit(code)
    except (OSError, ValueError, subprocess.CalledProcessError) as error:
        detail = error.stderr if isinstance(error, subprocess.CalledProcessError) else str(error)
        pause(f"Could not open PR chat: {detail or error}")
        sys.exit(1)
    except KeyboardInterrupt:
        sys.exit(130)
