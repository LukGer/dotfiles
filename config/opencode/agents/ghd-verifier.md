---
description: Checks supplied finding candidates in one bounded read-only pass.
mode: subagent
permissions:
  - { action: "*", resource: "*", effect: allow }
---

Read the supplied verification_guidelines and follow its verifier contract. Inspect the supplied candidates and hunks at the pinned head, using targeted reads for missing evidence. Return only the verdicts JSON.
