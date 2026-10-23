# Production risk

Find changes that can hurt a running system or its data when deployed, even when the code is correct. For each changed behaviour, identify the operational entry point that reaches it (job, endpoint, migration, startup, cron, consumer) and who is affected (customers, tenants, configurations, environments):

- Data: migrations that lock, rewrite or drop; backfills without batching; changed defaults or nullability; destructive operations without a dry run or a guard; irreversible transformations; mismatches between schema and code during a rolling deploy.
- Compatibility: API response shapes, event payloads, feature flags and config keys that old clients, other services or queued messages still rely on; renamed environment variables; removed endpoints.
- Rollout and rollback: can this ship behind a flag, can it be reverted without data loss, does it need an ordered deploy, does it change infrastructure or permissions?
- Failure modes: new external calls without timeouts, retries or circuit breaking; error handling that fails open or hides failures; changed logging and metrics that blind alerting; quota and cost (N+1 queries, fan-out, unbounded jobs).
- Performance: queries without indexes on the new access path, loops over whole tables, large payloads, blocking calls on hot paths, cache invalidation.
- Blast radius: shared utilities or base classes changed for one caller; global configuration edits; changes to auth, billing, notifications or anything that contacts customers.

A candidate states the entry point, the trigger and the consequence. Severity follows reach and reversibility: unrecoverable or customer-wide is `P0`/`P1`.
