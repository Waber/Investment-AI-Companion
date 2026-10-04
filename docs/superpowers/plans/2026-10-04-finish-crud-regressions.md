# Finish CRUD Regression Coverage

Completed: metric creation6 cases (full702), collector6 cases (full708), both
independently reviewed and scoped style checks passed. Six legacy warnings remain.
No production changes needed. Full September Task2 targeted scenarios are covered
across the prior commits and these two slices; PostgreSQL verification is separate.

Continue the approved September Task2 from `0008b0c` in two bounded commits.

1. Metric creation: duplicate tuple rejects without mutation; changing each key
   component allows creation; real FK/unique failures roll back and permit reuse
   of the same session. Test first; production changes only for reproduced bugs.
2. Collector: inject deterministic fake provider; existing company refresh retains
   identity and does not insert duplicates; absent provider result returns404
   without mutation for existing/missing companies. Verify returned IDs, fresh DB
   state, unrelated records, ticker normalization and repeat requests.

Each slice gets focused/full tests, scoped style checks, independent spec/quality
review and a local commit. Coordinator owns documentation; developers own disjoint
test files. No live provider calls, dependency upgrades, migrations or frontend.
If bugs require a wider contract decision, record them instead of expanding scope.

For this user-authorized session only, wrap up before90% consumed. Check account
usage after stages and preserve review/commit budget. No automatic credit reset.
