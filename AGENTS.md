# AGENTS.md

## About me

- I am a experienced test automation engineer who wants to expand his programming knowledge and skills. I code mostly in Java but want to learn Python so either you should 
- explain to me how your code works and/or document it in a way that a junior developer can understand. 

## Working Agreements

- Answer in the language used by the user. Keep code, identifiers, and technical documentation in English.
- Explain non-obvious implementation choices clearly enough for a developer still learning this codebase.
- Work on a dedicated branch for non-trivial changes.
- Keep changes focused, testable, and close to existing project patterns.
- Prefer small domain/service boundaries over broad rewrites.
- Do not remove user changes or untracked files unless explicitly requested.

## Git Workflow

Use rebase so history stays a straight line. Linear history is easier to read, bisect, and review than a graph of merge commits.

- Update a feature branch by rebasing onto the latest `origin/master` (`git fetch`, then `git rebase origin/master`). Never merge `master` into the feature branch.
- Pull with rebase (`git pull --rebase`, or `git config pull.rebase true` in this repository so later pulls rebase by default) so a routine update does not create a local merge commit.
- Before opening or updating a pull request, keep the branch's commits focused and meaningful. Tidying your own unpublished or feature-branch commits with interactive rebase is fine.
- After rebasing a feature branch that was already pushed, push only with `--force-with-lease`, and only on the agent's or author's own feature branch. Never force-push or rewrite history on `master` or on shared branches. On a branch someone else also pushes to, coordinate before rebasing, or rebase only right before merge.
- Integrate pull requests with GitHub's "Rebase and merge" so `master` stays linear. "Rebase and merge" is enforceable only when the repository has "Allow rebase merging" enabled (optionally with merge commits disabled); changing those repository settings is the user's decision, not an agent's. Agents must not merge a pull request unless the user explicitly authorizes it.
- If a rebase hits conflicts, resolve them carefully so both sides' intent is preserved, rerun the relevant tests, and if unsure stop and report rather than guessing.

## Journal And Delivery

- Update `docs/development-journal.md` for each delivered iteration.
- Record scope, decisions, verification commands, AI model used, and time tracking.
- For deeper tasks, use PM/Analyst, Engineer, and QA/Reviewer roles or subagents.
- If priorities change, record what is implemented and what remains in the backlog.

## Session Continuity And Checkpoints

- Check account usage before work and after each meaningful stage. At 80% consumed
  (or a different threshold explicitly set by the user for the current session)
  in either available usage window, stop starting tasks, checkpoint current work,
  and notify the user before continuing. Begin wrapping up earlier when needed
  to leave room for verification, review and commits. These are account limits,
  not a measurement of remaining conversation context. Never redeem a reset
  without explicit authorization; wait for the user's continuation after reset.

- At the start of a new session, read `docs/work-state.md`, the latest development journal entry, and the linked plan or review before choosing the next task.
- Before an anticipated context handoff, context compaction, usage-limit interruption, or user-requested pause, checkpoint at a safe boundary while tools are still available.
- Commit only the current task's deliberate changes on its working branch. A partial checkpoint must be clearly labeled WIP and must not be merged or described as finished. Preserve unrelated changes, secrets, local configuration, and untracked user files.
- Update `docs/work-state.md` with the branch, completed work, incomplete work, test results and unrun checks, active agents, blockers, and the exact next action. Keep this file current rather than accumulating conflicting snapshots.
- Record the actual checkpoint or stop reason. For an approaching usage limit, explicitly record that reason; use available usage information and do not invent a limit, credit balance, or reset time. Distinguish an anticipated pause from a limit already reached.
- Context compaction alone does not cancel the task. Resume from the checkpoint and continue authorized work when capacity is available; do not ask for approval again solely because context was compacted.
- When a session is interrupted too abruptly to commit, the next session must inspect the working tree and preserve unfinished changes before resuming.

## Security-audit skill

The Cloudflare `security-audit` skill in this repository is guidance unless the owner asks for a full audit. The files under `.agents/skills/security-audit/` are the upstream copy named in `skills-lock.json`. Do not edit those files, and do not replace the Claude Code link with a second copy of the tree. Either change would make the installed tree differ from the hash recorded in that lock file.

- A security question, a focused review, or a check of one finding stays in guidance mode. Do not start the multi-agent six-phase audit, create an audit output directory, or write audit report artifacts unless the owner explicitly asks for a full security audit or a pen-test of this repository or of a named path.
- Before that full audit, check account usage in every window this session can actually read. If usage is at or above 80%, or at or above a lower threshold the owner set for the session, do not start. Checkpoint and wait. If the usage meter is not available, say so. Do not invent a percentage, a balance, or a reset time, and do not start the full audit on a guessed figure.
- `.claude/skills/security-audit` is a Git symlink (index mode `120000`). The stored link text is `../../.agents/skills/security-audit` (35 bytes, no trailing newline). When the checkout can create symlinks, that path is a directory link, and Claude Code can read `SKILL.md` through it.
- Git checks a symlink out as a small plain file containing the link text when `core.symlinks` is false (`git help config`). `git clone` and `git init` set that value to false when their probe finds that this process cannot create a symlink. Git for Windows leaves symlink support off unless it detects that the user can create one (Developer Mode on a recent Windows 10, or `SeCreateSymbolicLinkPrivilege`). See https://gitforwindows.org/symbolic-links. `core.symlinks=true` does not create the link if that privilege is missing.
- On a checkout where `.claude/skills/security-audit` is a plain file, there is no `SKILL.md` inside a directory at that path, so Claude Code does not discover the skill there. Agents that read `.agents/skills/security-audit/` still do. Keep the symlink. A copied tree can drift from the lock hash.

## Investment Domain Rules

- Show source, data freshness, assumptions, risks, and uncertainty for market data, scores, AI analysis, and signals.
- Research write-ups use scenarios: base case, upside case, downside case, and thesis-breakers.
- The application, together with an agent, may issue buy and sell signals. Raul decided on 2026-10-10 that the product does not need a notice that this is not investment advice. Do not add that notice to new copy. The rule is recorded in `docs/product-requirements.md` section 12.
- The shipped `/ui` demo still contains the older disclaimer banner. That banner is no longer a product requirement.
- Never infer a private portfolio, risk tolerance, or investment style from unavailable chat history. Use explicit project data or user-provided inputs.
- Real portfolios and the later AI Portfolio stay explicit and editable. Do not put Raul's real holdings into a model prompt unless he includes them on that request. The AI Portfolio's own virtual cash and positions are inputs to the model that manages that portfolio.

## Quality Gates

- Add or update tests for behavior changes.
- Do not call live market-data providers in automated tests.
- Use deterministic fakes for external providers.
- Run the relevant pytest suite before claiming completion.
