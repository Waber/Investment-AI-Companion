# Financial Metric Update Regression Slice

Based on merged PR1 (`1e05ab1`), bounded subset of Task2 in the September plan.
No schema, dependency, runtime or live database changes are planned.

- [x] Developer: characterize partial numeric updates, zero values, explicit null,
  omission, mixed updates, empty payload and invalid values. Verify API and fresh
  persisted reads; preserve record identity and unrelated values.
- [x] Coordinator: run full tests and scoped formatting checks.
- [x] Independent reviewer: inspect tests and any reproduced bug before delivery.
- [x] Coordinator: update work state/journal, commit the completed slice.

Results:82 new cases, full693 passed with six existing warnings. Scoped Black,
isort and flake8 passed; Aristotle approved specification and quality. No
production changes were needed; no live PostgreSQL/provider validation claimed.

Existing behavior may pass immediately: these are characterization tests, not
evidence of a newly fixed defect. Any production fix requires a failing test first.
Uniqueness/rollback and collector coverage remain separate subsequent slices.
Check usage after stages; close out before the user's80% usage boundary.
