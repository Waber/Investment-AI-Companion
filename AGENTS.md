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

## Journal And Delivery

- Update `docs/development-journal.md` for each delivered iteration.
- Record scope, decisions, verification commands, AI model used, and time tracking.
- For deeper tasks, use PM/Analyst, Engineer, and QA/Reviewer roles or subagents.
- If priorities change, record what is implemented and what remains in the backlog.

## Session Continuity And Checkpoints

- Check account usage before work and after each meaningful stage. At 80% consumed
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

## Investment Domain Rules

- This app supports investment research and decision hygiene; it must not present outputs as financial advice.
- Show source, data freshness, assumptions, risks, and uncertainty for market data and AI analysis.
- Prefer scenarios over imperative buy/sell language: base case, upside case, downside case, and thesis-breakers.
- Never infer a private portfolio, risk tolerance, or investment style from unavailable chat history. Use explicit project data or user-provided inputs.
- Keep investor preferences explicit and editable when that feature is implemented.

## Quality Gates

- Add or update tests for behavior changes.
- Do not call live market-data providers in automated tests.
- Use deterministic fakes for external providers.
- Run the relevant pytest suite before claiming completion.
