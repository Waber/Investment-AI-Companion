# Pagination bounds on list endpoints (#19) Implementation Plan

**Spec:** GitHub issue #19 (`gh issue view 19`). Negative `skip`/`limit`
are accepted on the three list endpoints, SQLite treats `LIMIT -1` as
"no limit", and `limit` has no upper bound.

**Goal:** `skip >= 0` and `1 <= limit <= MAX_PAGE_LIMIT` on every list
endpoint, with out-of-range values rejected as HTTP 422. The default page
size stays 100.

**Out of scope:** cursor pagination, total-count headers, changing default
page sizes, repository-level guards, the `/ui` pages.

## Global Constraints

- Branch `fix/pagination-bounds-19`. Never commit to `master`, never push,
  never open or merge a pull request.
- `MAX_PAGE_LIMIT = 1000` (the value proposed in the issue). The default
  `limit` stays `100`, the default `skip` stays `0`.
- One shared constant for the maximum, used by all three endpoints:
  `GET /api/v1/companies/`, `GET /api/v1/financial-metrics/`,
  `GET /api/v1/financial-metrics/company/{company_id}`.
- FastAPI `Query(ge=..., le=...)` constraints. Out-of-range values return
  422 through the existing validation error handler. Do not hand-roll
  checks inside the endpoint bodies.
- `scripts/seed_demo.py` pages with `limit=100`; it must keep working.
- TDD: write the failing tests first, run them, record RED, then implement.
- No automated test reaches the network.
- Code and docs are read by a Java developer who is learning Python:
  explain a non-obvious Python or FastAPI idiom (for example
  `typing.Annotated` metadata) in a short comment or docstring, matching
  the comment density of the surrounding code.
- Commit messages use the repository's prefixes (`fix:`, `test:`,
  `docs:`), are imperative, and end with the trailer line
  `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`.

## Task 1: Bound skip and limit on the three list endpoints

**Files:**
- Create: `app/api/pagination.py` (the shared constants and the reusable
  query-parameter types)
- Modify: `app/api/companies.py` (list endpoint, currently line 44)
- Modify: `app/api/financial_metrics.py` (list endpoints, currently lines
  57 and 104-105)
- Create: `tests/test_pagination_bounds.py`
- Modify: `docs/development-journal.md`, `docs/work-state.md`
- Modify, only if they document page sizes: `docs/api-demo.md`,
  `README.md`

**Steps:**

1. Write `tests/test_pagination_bounds.py` first, using the `client`
   fixture from `tests/conftest.py`. Parametrize over the three endpoints.
   For `/financial-metrics/company/{company_id}`, create a company first
   so the path is valid. Cases:
   - `skip=-1` returns 422.
   - `limit=-1` returns 422.
   - `limit=0` returns 422.
   - `limit=MAX_PAGE_LIMIT + 1` (1001) returns 422.
   - `limit=MAX_PAGE_LIMIT` (1000) returns 200.
   - `skip=0&limit=1` returns 200.
   - No parameters returns 200 and still applies the default page size of
     100. Prove this with 101 rows on at least one endpoint: 100 come back.
   - The 422 body names the offending parameter (`loc` contains `query`
     and `skip` or `limit`).
   Import `MAX_PAGE_LIMIT` from the new module so the test follows the
   constant. Run the file and record the RED output (the import fails or
   the new cases return 200).
2. Create `app/api/pagination.py` with `DEFAULT_PAGE_LIMIT = 100`,
   `MAX_PAGE_LIMIT = 1000`, and two reusable parameter types built with
   `typing.Annotated[int, Query(...)]` for skip (`ge=0`) and limit
   (`ge=1`, `le=MAX_PAGE_LIMIT`), each with a short `description` that
   shows up in `/docs`. A module docstring explains why the bounds exist
   (#19: SQLite treats `LIMIT -1` as unlimited).
3. Use those types in the three endpoints. Keep the defaults (`skip=0`,
   `limit=DEFAULT_PAGE_LIMIT`).
4. Run the new file (GREEN), then the existing pagination tests that
   already cover skip/limit, then the full CI command.
5. Scoped lint on every changed `.py` file: `black --check`,
   `isort --check-only`, `flake8`.
6. Add a journal entry at the top of `docs/development-journal.md` and a
   section at the top of `docs/work-state.md`, in the same short style as
   the existing entries. The journal entry records: scope, the
   `MAX_PAGE_LIMIT = 1000` decision and that it awaits the owner's or the
   Code Reviewer's OK in the pull request (the issue requires it), the
   verification commands with their exact results, AI model (Claude
   Sonnet 5.5 implementer via Claude Code, Claude Opus 5.5 controller),
   time tracking (started 2026-10-12 about 14:40 +0200), and that account
   usage was not available in this session. The work-state section records
   branch, base `25e7eba`, completed, incomplete, tests, active agents
   (none after you finish), blockers, and the next action: "Code Reviewer
   review, then open the pull request (Closes #19)".
7. Commit the code and tests, and commit the docs separately.
