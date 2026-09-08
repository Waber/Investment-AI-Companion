# Current Work State

## Checkpoint

- Date: 2026-09-08.
- Reason: user-requested session continuity checkpoint while work continues. No current usage-limit stop.
- Working branch: `feature/research-workflow-and-hardening`.
- Base: published `master` at `6e1f2fc`.
- Primary repository: `/Users/przemkowy/IdeaProjects/Investment-AI-Companion`.
- Current isolated worktree: `/private/tmp/investment-remaining-work`.
- The saved Codex project named `InvestmentAiCompanion` still points at an older directory under `PycharmProjects`; it is not the repository above.

## Completed

- Baseline guidance, refactoring, tests, and all three review fixes were reviewed, committed, merged into `master`, and pushed to GitHub.
- Baseline verification: 537 pytest cases passed, with six known deprecation warnings. Default Black/isort/flake8 checks pass for tests.
- Added the checkpoint rules in `AGENTS.md` and this continuation file. This checkpoint changes documentation only.

## Authorized Work In Progress

The user requested continuing all remaining work from [the baseline review](reviews/2026-09-08-baseline-review.md#remaining-work):

1. Return a valid validation error for overflowing JSON numbers without saving invalid data.
2. Modernize deprecated FastAPI/Pydantic/SQLAlchemy usage and resolve existing application formatting/import debt.
3. Add and run isolated PostgreSQL integration tests.
4. Add regression coverage for startup/lifespan, update paths, and relevant configuration/CORS behavior.
5. Implement explicit, editable investor preferences and a source-aware AI analysis workflow.

## Open Questions And Constraints

- The user supplied explicit demo-profile preferences: investment horizon over ten years; broad geographic scope including Poland, the United States, Europe, and Asia; moderate-to-high risk tolerance; stocks, bonds, ETFs, and ETCs; no direct derivatives such as futures or CFDs.
- These preferences are an editable demo profile, not global application policy. The user explicitly requires changing parameters and supporting other investor profiles in future. Do not invent holdings, allocations, or a private portfolio.
- Preserve the existing untracked `.python-version` in the primary checkout.
- Continue with separate developer agents and an independent reviewer, on isolated branches/worktrees. No agents have been dispatched for this new iteration yet.
- No PostgreSQL server or live AI-provider call has been verified for this iteration. Do not describe those checks as complete.

## Next Action

Finish inspecting the current configuration, persistence, collectors, and local database/runtime availability. Write a scoped design and implementation plan that separates backend hardening, PostgreSQL verification, and the investor-analysis workflow. Dispatch independent technical tasks with disjoint file ownership, then integrate and independently review them. Update this file at each meaningful handoff or interruption.

## Verification For This Checkpoint

- Documentation-only change; no application test run required.
- Check staged whitespace and scope before commit.
- When updating this file after an interruption, replace this snapshot with the actual state and state the exact stop reason.
