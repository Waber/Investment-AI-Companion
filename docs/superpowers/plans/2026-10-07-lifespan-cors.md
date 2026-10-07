# Lifespan And CORS Delivery

Approved scope: finish the bounded runtime/CORS slice, verify, push and open a PR
against master. Do not merge. Include the five unpublished ancestor commits.

## Implementation

- Developer: replace deprecated startup registration with an async lifespan.
- Call the existing init_db boundary, preserve disabled initialization for tests,
  and propagate initialization failures instead of serving a broken application.
- Normalize the URL-added trailing slash for exact browser-origin matching.
  Preserve credentials policy and do not broaden the allowlist.
- Tests first: successful/disabled/failing startup and allowed/denied simple and
  preflight CORS requests, including empty configuration. No real providers/DBs.

## Delivery Gates

- Independent reviewer checks correctness, isolation and regression coverage.
- Coordinator runs full pytest and scoped style checks, updates startup guide,
  journal and current state, commits, pushes and creates the PR.
- Check account usage after meaningful stages. Default 80% checkpoint boundary;
  finish well before it. Do not redeem a reset or start further backlog work.

## Deferred

Pydantic/SQLAlchemy deprecation cleanup, Alembic/PostgreSQL integration, editable
profiles and source-aware AI remain separate tasks. No dependency upgrades here.
