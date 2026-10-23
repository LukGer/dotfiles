# Correctness

Find behaviour that is wrong for some reachable input or state. Work hunk by hunk and ask of each change:

- Does every branch, loop and early return do what the surrounding code and the PR description promise? Walk one concrete input through the new path and one through the old.
- Boundaries: empty collections, zero, negatives, the last index, unicode, time zones and DST, leap and month ends, very large values, concurrent calls.
- Nullability and optionality: values that can be absent, default parameters, destructuring of possibly undefined objects, `??` versus `||`.
- Async: unawaited promises, errors swallowed by `.catch` or empty `try`, races between reads and writes, cancellation and timeouts, retries without idempotency.
- Types and conversions: string versus number ids, truthiness of `0` and `""`, float money, implicit coercion at API edges, enum exhaustiveness after a new member.
- State: mutation of shared or cached objects, stale closures, ordering assumptions, initialisation before use, cleanup on every exit path.
- Contracts: callers of changed signatures and renamed fields (search for them), serialised shapes that persist or cross a wire, tests that now assert the wrong thing.

Every candidate traces to a concrete failing input or sequence. Suspicions without a path to failure are `dropped` with that reason.
