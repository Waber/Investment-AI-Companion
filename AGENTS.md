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
