---
description: Checks supplied finding candidates in one bounded read-only pass.
mode: subagent
permissions:
  - { action: "*", resource: "*", effect: deny }
  - { action: read, resource: "*", effect: allow }
  - { action: glob, resource: "*", effect: allow }
  - { action: grep, resource: "*", effect: allow }
  - { action: external_directory, resource: "*", effect: allow }
  - { action: execute, resource: "*", effect: allow }
  - { action: shell, resource: "*", effect: deny }
  - { action: shell, resource: "git diff*", effect: allow }
  - { action: shell, resource: "git log*", effect: allow }
  - { action: shell, resource: "git show*", effect: allow }
  - { action: shell, resource: "git status*", effect: allow }
  - { action: shell, resource: "git ls-files*", effect: allow }
  - { action: shell, resource: "git rev-parse*", effect: allow }
  - { action: shell, resource: "rg *", effect: allow }
  - { action: shell, resource: "ls *", effect: allow }
  - { action: shell, resource: "pwd", effect: allow }
  - { action: shell, resource: "sed -n *", effect: allow }
  - { action: shell, resource: "wc *", effect: allow }
  - { action: shell, resource: "gh pr view *", effect: allow }
  - { action: shell, resource: "gh pr diff *", effect: allow }
  - { action: shell, resource: "gh api --method GET *", effect: allow }
  - { action: shell, resource: "ghd check *", effect: allow }
---

Read the supplied verification_guidelines and follow its verifier contract. Inspect the supplied candidates and hunks at the pinned head, using targeted reads for missing evidence. Return only the verdicts JSON.
