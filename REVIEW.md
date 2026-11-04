# REVIEW.md

Guidance for anyone who reviews a pull request in this repository,
whether an AI reviewer or a person. `AGENTS.md` says what the project
is and how we work. This file says what matters in a review.

It follows the lessons in
[How the Claude Code team does code review](https://claude.dev/blog/solving-code-review-at-anthropic/)
(Anthropic, 2026-10-15): keep the file short, say what failure looks
like here, cap the nits, list the paths to skip, ask for evidence, and
start the summary with a count.

## What failure looks like here

Report these as **Important**. Each one is a bug, even when the tests
are green.

1. **A number lies.** A price, money amount, or score is shown without
   its source or freshness. Stale or demo data looks fresh or real. A
   price or money amount is stored, compared, or summed as `float`
   instead of `Decimal`. A timestamp is naive instead of aware UTC
   (`app/core/utc_datetime.py`).
2. **A save goes wrong.** A write is stored twice, half done, or lost.
   For example, an HTMX retry or a plain-form fallback re-sends a
   create POST. A batch behaves differently on SQLite and PostgreSQL.
   Alembic has more than one head, or a migration cannot run on an
   existing database.
3. **A page becomes unsafe.** User text reaches HTML through `|safe`
   or `Markup`. The CSP in `app/ui/router.py` needs an inline style or
   script. A state-changing `/ui` route skips `require_same_origin`
   (`app/ui/origin.py`). A redirect target comes from the request. User
   text skips the bounds and checks in `clean_text`
   (`app/validation/text.py`).
4. **Private data leaks.** Raul's real holdings go into a model prompt
   without him adding them to that request. A secret, `.env`, or local
   configuration is committed. A test calls a live market-data provider
   instead of a deterministic fake.
5. **The UI breaks for someone.** An HTMX action has no plain-form
   fallback. A key is missing from the PL or EN catalog
   (`app/ui/catalog.py`). A control has no label, or focus is lost
   after an action.
6. **Docs lie.** A docstring, the API guide, `README.md`, or
   `docs/work-state.md` says something the code does not do.
7. **The PR body misroutes.** `Closes #N` (or "fixes" or "resolves")
   appears for an issue the PR does not finish. "does not close #N"
   still closes #N on merge. Use `Refs #N` for everything else.

## Severity

- **Important**: one of the failures above, or a bug a user or the
  stored data would hit. It blocks the merge until it is fixed or
  answered.
- **Nit**: naming, wording, or a small simplification. A nit never
  blocks, however many there are. Report the three most useful and
  drop the rest.
- **Pre-existing**: a bug in code this PR did not change. Tag it, so it
  does not look like the author's fault, and suggest a follow-up issue
  instead of a fix in this PR.

Do not report what black, isort, flake8, or CI already enforce.

## Evidence

- Every finding names a file and line, the input or state that triggers
  it, and what goes wrong. A guess from a function name is not a
  finding. Read the code. If you cannot point to a line, ask a
  question instead.
- On a bug fix, check that the root cause is fixed, not only the
  symptom from the issue.
- Flag the class of bug. When the same mistake appears in several
  places, report it once and list every location, so the author fixes
  all of them in one round.
- A behaviour change needs a test that fails without the change. The PR
  body says how the change was tested (the command and its result) and
  how to undo it.

## Paths

Skip these, apart from checking that the change was intended:

- `static/vendor/` (vendored htmx);
- `requirements.lock` and `requirements-dev.lock` (generated);
- `fixtures/*.json` (check the shape, not every row);
- old entries in `docs/development-journal.md` (review only the new
  entry).

These always need Raul's review, whatever the automated review says:

- `alembic/versions/`;
- `.github/workflows/`;
- `app/ui/origin.py` and the security headers in `app/ui/router.py`;
- `app/core/config.py`, `.gitleaks.toml`, and the lock files when a
  dependency changes;
- `app/data_collectors/guard.py` and `app/data_collectors/call_budget.py`;
- any code that sends data to an AI model.

An agent's review never counts as Raul's approval, and agents never
merge.

## Rounds

- Every finding gets an answer. The author fixes it, or resolves the
  thread with a reason: a false positive, intentional, or deferred to
  issue #N.
- After the first round, review only the diff since the last review.
  Do not repeat a finding that was already posted or answered.
- After three rounds that still have Important findings open, stop. Ask
  the author to step back and reconsider the approach instead of
  starting a fourth fix round.
- Raise a question about direction or scope early, in the issue or the
  spec, not as a blocking comment on a finished PR.

## Summary

Start with the count, for example "2 Important, 1 Nit, 0 Pre-existing".
When there is nothing to fix, say "Nothing to fix." plainly, without
filler. Then list the findings, most severe first. End with what the
review did not check, such as "the UI was not driven in a browser" or
"PostgreSQL was not run locally", so the person who approves knows what
the checks would miss.

## Keeping this file useful

- When the same review comment appears on two PRs, move it here, or
  better, into a test or a lint rule.
- When a bug reaches `master`, ask which check should have caught it,
  and add that check here or as a test.
- Keep this file short. If a section grows past a screen, move the
  detail to the doc it belongs to and link to it.
