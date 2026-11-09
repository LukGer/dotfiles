---
name: babysit
description: Use when asked to babysit, monitor, shepherd, or keep working on a GitHub pull request until it is green, review-ready, approved, mergeable, or ready to merge.
---

# Babysit

Use this skill to stay with a PR after it has been opened or while it is waiting on CI, reviews, mergeability, or small follow-up fixes.

The goal is: keep the PR moving until it is ready to merge while preserving its original purpose. Do not merge unless the user explicitly asks.

## Start

1. Identify the PR.
    - Prefer the current branch's PR: `gh pr view --json number,url,title,headRefName,baseRefName,state,isDraft,mergeStateStatus,reviewDecision,statusCheckRollup`.
    - If there is no PR for the current branch, ask for the PR URL or number.
    - If the PR is closed or merged, report that and stop.
2. Establish the original goal and acceptance criteria from the user's request, linked issue, PR description, and diff. Summarize them briefly and use them as the baseline throughout the loop. Ask only if conflicting evidence prevents a safe next step.
3. State the current blocker in one short update:
    - draft PR
    - failing or pending checks
    - merge conflicts or stale branch
    - review requested
    - changes requested
    - ready to merge
4. If the PR is already ready to merge, report the URL and stop.

## Scope and Deferral

-   Before each fix, explain how it supports the original goal or resolves a demonstrated blocker. Use the smallest complete fix that preserves the intended behavior.
-   Evaluate review comments and automated findings against the code and requirements. They are evidence, not authorization to expand the PR's scope; optional suggestions and neutral monitor findings need not become blockers.
-   Defer nonblocking work that is not security-relevant, such as unrelated cleanup, refactoring, or enhancements, to a follow-up ticket. Record the finding, why it can wait, and acceptance criteria; link the ticket in the final report. If ticketing is unavailable, report the proposed follow-up explicitly as unfiled.
-   Assess security findings before considering deferral. Escalate unresolved security risks, data-loss risks, and correctness issues that prevent the original goal from being met; ask for a decision if resolving them would expand scope.
-   A follow-up ticket does not waive a required check or blocking review. If deferral needs a reviewer or maintainer decision, report that blocker and ask for the decision.
-   Reassess the cumulative diff after each fix and whenever a new failure appears. If the work would change the original goal, add a feature, change unrelated behavior, or require a broader product or architectural decision, summarize the evidence and ask before proceeding.

## Readiness Definition

Treat a PR as ready to merge when all of these are true:

-   The PR is open and not a draft.
-   Required checks are passing.
-   There are no merge conflicts.
-   The branch is current enough for GitHub to report it mergeable or clean.
-   Reviews are approved, or the repo does not require approval.
-   There are no unresolved requested changes or blocking reviewer comments.

If GitHub's mergeability is temporarily unknown, wait and re-check before calling the PR ready.

## Macroscope Monitors

Macroscope monitors are reviewers that focus on particular areas of the code. They are check that return `conclusion: neutral`, but post a PR comment with a score and an explanation of what they found. Make sure you read the results of all the monitors and take their feedback into account.

## Loop

Repeat until the PR is ready to merge, blocked on a human decision, or the user stops you.

1. Refresh PR state.
    - `git fetch origin`
    - `gh pr view --json number,url,title,headRefName,baseRefName,state,isDraft,mergeStateStatus,reviewDecision,statusCheckRollup,reviews,comments`
    - `gh pr checks` or `gh pr checks --watch` when checks are pending.
2. Handle the highest-priority blocker first.
    - **Draft:** ask before marking ready for review unless the user already asked you to make it ready.
    - **Merge conflicts or stale base:** rebase or merge from the base branch using the repo's normal style. Prefer the existing branch style if visible in history. Ask before force-pushing rewritten history unless the user already explicitly authorized force-pushes for this PR.
    - **Failed checks:** inspect the failing job logs with `gh run view --log-failed` or the relevant provider logs. Apply the scope and deferral rules, fix the root cause when in scope, run focused local validation, commit, and push.
    - **Changes requested:** read review comments, apply the scope and deferral rules, make the requested changes when they are clear and appropriate, run focused validation, commit, and push. If a requested change is ambiguous, product-sensitive, or contradicts repo conventions, ask the user.
    - **Pending checks:** wait for the existing run instead of starting duplicate long-running validation. If a check appears stuck, report the stuck check and elapsed time before retrying or asking.
    - **Pending review:** leave a concise status for the user. Do not pester reviewers from the agent unless the user asks.
3. After each push, wait for checks to start and then continue monitoring.
4. Keep updates brief and factual: what changed, what is currently running, and the next check you are waiting for.

## Fixing Rules

-   Read the relevant code before changing it.
-   Preserve unrelated worktree changes.
-   Prefer focused validation before broad validation; run broader validation when the fix touches shared behavior.
-   If a validation command is already running, wait for it or abandon it explicitly before starting another copy.
-   If the same check fails twice for the same unclear reason, summarize the evidence and ask for help.
-   If the PR requires a secret, external account, paid service, protected branch action, or reviewer decision that the agent cannot access, stop with the exact blocker.
-   If an agent (e.g. Macroscope) commented on the PR and you believe it was mistaken, you can reply to its comment (signing the reply with your name).

## Useful Commands

```bash
git status --short
git fetch origin
gh pr view --json number,url,title,headRefName,baseRefName,state,isDraft,mergeStateStatus,reviewDecision,statusCheckRollup,reviews,comments
gh pr checks
gh pr checks --watch
gh run view <run-id> --log-failed
```

## Stopping States

Stop and report when:

-   The PR is ready to merge.
-   A human decision is required.
-   A protected action is required.
-   CI or GitHub is unavailable long enough that waiting is no longer useful.
-   The user asks you to stop.

Final response format:

-   PR URL.
-   Current state: ready to merge, blocked, or still failing.
-   What you fixed or verified.
-   Deferred work and follow-up ticket links, identifying any unfiled follow-ups.
-   Any remaining human action.
