# Deep correctness

An independent second pass on the exact hunks named in your scope, kept separate from any other pass: do not read other passes' results. Trace each hunk's dependencies both ways:

- Upstream: every caller and every producer of its inputs. Which assumptions about shape, ordering, uniqueness or non-emptiness does the new code make, and does every producer honour them?
- Downstream: every consumer of its outputs, including persisted data, events, caches and other services. What changes for them when the new code returns something different, throws, or returns early?
- Invariants: identify the two or three invariants this code must keep (uniqueness, totals that balance, state machine transitions, idempotency) and show for each whether the change preserves it.
- Failure paths: partial writes, exceptions between two related mutations, retries replaying side effects, concurrent executions of the same path.
- Tests: do the changed or added tests exercise the new branches with inputs that would fail against the old code? Name the missing case.

Report only verified candidates with the chain of evidence (file:line at each step). Breadth belongs to the correctness pass; your value is depth on these hunks.
