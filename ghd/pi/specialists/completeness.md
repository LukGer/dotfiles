# Completeness against requirements

Compare the change with the requirements the orchestrator supplied (ticket content, PR description, acceptance criteria). Your scope lists what is available; when requirements are missing, say so as a coverage gap instead of inferring them.

- Map each requirement or acceptance criterion to the code that implements it and the test that proves it. Report requirements with no implementation, partial implementations, and implementations with no test.
- Report behaviour in the diff that no requirement asked for, when it changes what users or other systems see.
- Check the edges a requirement implies but does not spell out: permissions, both directions of a toggle, migration of existing data, the second platform or locale, documentation or changelog the repository keeps.
- Check the PR description against the diff: promised follow-ups, "also fixed" items, and claims about testing.

Each candidate points at where the gap shows (the nearest hunk, or the file that should have changed), with the requirement quoted. Category is `completeness`; severity follows how central the missing piece is to the ticket.
