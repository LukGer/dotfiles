# Quality and maintainability

Find changes that will cost the next maintainer. Judge against the repository's own conventions (read neighbouring code and any contributing or style guide you can find) rather than personal taste:

- Duplication: logic that already exists in the repository, copy-pasted blocks with small variations, parallel data structures that must be kept in sync.
- Naming and intent: names that lie or are vague, booleans with negative names, functions doing more than their name says, comments that restate the code or contradict it, dead code and leftover debugging, double casts (`as unknown as`) that hide the real shape.
- Size and shape: oversized functions and files, deep nesting, long parameter lists, mixed abstraction levels, side effects hidden in getters.
- Sibling parity: a new screen, route, handler or command that diverges from the existing ones with the same shape (data loading, guards, mutations and cache invalidation, file layout, validation location). Cite file:line on both sides; a divergence without a comparator anchor is not a finding.
- Rebuilt pieces: a new component, hook or helper that already exists. Search shared component, util and query directories before calling something new; byte-identical strings or messages across files are the giveaway.
- Errors: swallowed exceptions, generic catches, error messages without context, inconsistent error types.
- Tests: missing tests for new behaviour, tests that cannot fail, tests coupled to implementation details, flaky patterns (time, randomness, ordering, network).
- Types and APIs: `any` or casts that hide a real type problem, public surface widened without need, inconsistent option shapes, breaking changes to internal contracts without updating callers.
- Repository hygiene: generated files, lockfile churn, formatting-only noise mixed into logic changes, missing or stale documentation for changed behaviour.

Most candidates here are `P2` or `P3`; use `P1` only when the problem will plausibly cause a bug soon. Prefer one finding with the pattern and its occurrences over one finding per occurrence.
