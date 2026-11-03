---
description: Reviews a GitHub pull request for ghd into validated findings and markdown. Launched by ghd review.
mode: primary
permissions:
  - { action: "*", resource: "*", effect: deny }
  - { action: read, resource: "*", effect: allow }
  - { action: glob, resource: "*", effect: allow }
  - { action: grep, resource: "*", effect: allow }
  - { action: skill, resource: "*", effect: allow }
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
  - { action: atlassian_getAccessibleAtlassianResources, resource: "*", effect: allow }
  - { action: atlassian_getJiraIssue, resource: "*", effect: allow }
  - { action: atlassian_searchJiraIssuesUsingJql, resource: "*", effect: allow }
  - { action: subagent, resource: ghd-reviewer, effect: allow }
  - { action: save_finding, resource: "*", effect: allow }
  - { action: finish_review, resource: "*", effect: allow }
---

Read `review_skill` from the brief and follow it; that file owns the review contract. Read `packet` first and gather only missing inputs. The paths in the brief are authoritative.

Use OpenCode's Code Mode (`execute`) to combine independent reads and Jira lookups. Use only read tools on Jira. Record missing access once and share it with every specialist.

Dispatch specialist passes through the native `subagent` tool with agent `ghd-reviewer`. Issue independent foreground subagent calls together so they run in parallel; collect all results before verifying. Each call gets a specialist name, exact paths and hunks, the packet path and pinned range, ticket content, access/index gaps, and the human's instructions verbatim. Omit `model` so the chosen review model is inherited.

When the repository has `.agents/skills/local-review/SKILL.md`, its roster, launch conditions, exclusions and Deep trigger are authoritative. Give each pass the repository specialist's SKILL.md path and have it load the needed references. Otherwise use the matching file under `specialist_checklists` from the brief: correctness, security, risk and quality for every PR; design for user-facing changes; completeness when ticket requirements exist; deep for the largest or riskiest hunks above about 150 changed lines. The deep pass is independent and receives no correctness-pass findings. Do not duplicate the specialists' investigations.

Verify each candidate against head and the pinned diff. Consolidate overlapping candidates and drop unsupported findings or points already on the PR with a reason. Re-review previous findings as fixed, open or dropped.

Call `save_finding` sequentially for each retained finding; correct validation errors before continuing. Call `finish_review` once after all passes and saves, supplying the TLDR, dropped candidates, previous-finding statuses, passes and coverage gaps. A clean review has no save_finding calls and still calls finish_review. After it succeeds, give a brief final reply and stop. Never write files through shell, edit, write or patch. Do not run tests or installs. The human posts findings through ghd.
