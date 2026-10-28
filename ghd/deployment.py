#!/usr/bin/env python3
import argparse
import json
import subprocess
import sys

from ui import choose, pause


QUERY = """
query($owner: String!, $name: String!, $number: Int!, $endCursor: String) {
  repository(owner: $owner, name: $name) {
    pullRequest(number: $number) {
      headRefOid
      mergeCommit { ...DeployedCommit }
      potentialMergeCommit { ...DeployedCommit }
      commits(first: 100, after: $endCursor) {
        nodes {
          commit { ...DeployedCommit }
        }
        pageInfo { hasNextPage endCursor }
      }
    }
  }
}
fragment DeployedCommit on Commit {
  oid
  deployments(last: 100) {
    nodes {
      environment state createdAt
      latestStatus { environmentUrl }
    }
  }
}
"""


def fetch_deployments(repo, number):
    owner, name = repo.split("/", 1)
    command = ["gh", "api", "graphql", "-f", f"query={QUERY}", "-f", f"owner={owner}",
               "-f", f"name={name}", "-F", f"number={number}"]
    deployments = []
    cursor = []
    while True:
        result = subprocess.run([*command, *cursor], capture_output=True, text=True, check=True)
        payload = json.loads(result.stdout)
        if payload.get("errors"):
            raise RuntimeError("; ".join(error["message"] for error in payload["errors"]))
        repository = payload["data"]["repository"] or {}
        pr = repository.get("pullRequest")
        if not pr:
            raise RuntimeError(f"PR not found: {repo}#{number}")
        commits = [node["commit"] for node in pr["commits"]["nodes"]]
        if not cursor:
            commits.extend(pr[field] for field in ("mergeCommit", "potentialMergeCommit") if pr.get(field))
        deployments.extend((deployment, commit["oid"])
                           for commit in commits for deployment in commit["deployments"]["nodes"])
        page = pr["commits"]["pageInfo"]
        if not page["hasNextPage"]:
            return pr, deployments
        cursor = ["-f", f"endCursor={page['endCursor']}"]


def main():
    parser = argparse.ArgumentParser(description="Open a PR's active deployment.")
    parser.add_argument("repo", help="owner/repo")
    parser.add_argument("pr", type=int)
    args = parser.parse_args()
    pr, deployments = fetch_deployments(args.repo, args.pr)
    deployments.sort(key=lambda item: item[0]["createdAt"], reverse=True)
    if not deployments:
        pause(f"No deployments associated with {args.repo}#{args.pr}.")
        return 1
    environments = {}
    for deployment, sha in deployments:
        status = deployment.get("latestStatus") or {}
        url = status.get("environmentUrl") or ""
        if deployment["state"] != "ACTIVE" or not url.startswith(("https://", "http://")):
            continue
        revision = "current commit" if sha == pr["headRefOid"] else f"earlier commit {sha[:7]}"
        if any(pr.get(field) and sha == pr[field]["oid"] for field in ("mergeCommit", "potentialMergeCommit")):
            revision = f"merge commit {sha[:7]}"
        environments.setdefault(deployment["environment"],
                                f"{deployment['environment']} ({revision})\t{url}")
    choices = list(environments.values())
    if choices:
        selected = choices[0]
        if len(choices) > 1:
            picked = choose("Deployment", [{"label": choice.split("\t", 1)[0],
                                            "preview": choice.split("\t", 1)[1]} for choice in choices])
            if picked is None:
                return 0
            selected = choices[picked]
        label, url = selected.split("\t", 1)
        print(f"Opening {label}: {url}")
        subprocess.run(["open", url], check=True)
        return 0
    message = ["No active deployment URL is available:"]
    seen = set()
    for deployment, _ in deployments:
        if deployment["environment"] in seen:
            continue
        seen.add(deployment["environment"])
        message.append(f"  {deployment['environment']}: {deployment['state']}")
    pause("\n".join(message))
    return 1


if __name__ == "__main__":
    message = None
    try:
        code = main()
    except subprocess.CalledProcessError as error:
        message = error.stderr or f"{error.cmd[0]} failed ({error.returncode})."
        code = 1
    except (OSError, ValueError, RuntimeError) as error:
        message = str(error)
        code = 1
    if message:
        print(message, file=sys.stderr)
        if sys.stdin.isatty() and sys.stdout.isatty():
            pause(message)
    sys.exit(code)
