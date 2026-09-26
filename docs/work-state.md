# Current Work State

- Date: 2026-09-26. User requested a running local demo and API request documentation.
- Branch: `chore/local-api-demo`, based on `731c513`. Worktree: `/private/tmp/investment-api-demo`.
- Primary repo remains `/Users/przemkowy/IdeaProjects/Investment-AI-Companion`; its `master` and untracked `.python-version` are untouched.
- Demo: `http://127.0.0.1:8081/docs`, API on port8081 loopback only, no authentication. Never expose publicly.
- PostgreSQL14.19: fresh cluster `/private/tmp/iac-demo.h7TbGw/data`, private socket directory `/private/tmp/iac-demo.h7TbGw`, port15432, no TCP listener, role `demo`, database `investment_demo`.
- API runs detached with PID in `/private/tmp/iac-demo.h7TbGw/api.pid`, log `api.log`; database log `postgres.log` in the same directory. These are intentional demo services, not unfinished test processes. Stop/restart commands are in [the demo guide](api-demo.md).
- Environment is isolated, DEBUG=False, no private `.env` or API keys. Existing installed interpreter used; no dependency upgrade or user DB migration.
- Synthetic sample company `DEMO` and metrics were created successfully (initial IDs both1). No real market/provider calls or AI analysis.
- Fresh regression run: 549 passed, six existing warnings. Live PostgreSQL startup, company insert, and metrics insert succeeded. Final smoke and review are recorded in the journal.
- Starting usage:60% five-hour/26% weekly used; after launch:73%/28%. These are account limits, not remaining-context measurements. No reset or purchase.
- Developer Curie owns demo guide and smoke client; independent review before local commit. No push/merge authorized.
- Demo guide and smoke complete; coordinator verified live PostgreSQL smoke and script style. Ohm's curl proxy/config finding corrected. Final commit was interrupted by quota, now resumed by user request. No reset was redeemed. Runtime remains active; no production changes.
- Temporary directories can disappear after cleanup/reboot. Git preserves code/docs, not the temporary demo database. Do not keep valuable data here.

## Remaining Work

- Missing-update404 and website-update regressions are complete in ancestors `3a2b0af` and `731c513`.
- Metric partial-update/null, uniqueness/rollback and collection regression coverage; JSON overflow handling; lifecycle/CORS/deprecation cleanup; guarded migrations and automated PostgreSQL integration tests remain pending.
- Editable profiles and source-aware AI analysis remain unimplemented. Demo preferences are preserved in the approved September8 design/plan, not yet implemented.
- Prior WIP dependency pin on `feature/research-workflow-and-hardening` conflicts with FastAPI and is NOT in this branch. Do not merge blindly.
- This manually exercised PostgreSQL demo is not completion of the migration/integration-test task. Financial-metrics provider ingestion is still a placeholder.
- Next authorized development slice: metric partial-update/null regressions. Keep the running demo stable; develop in another isolated worktree.
