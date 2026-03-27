# RULE PATCH — Dependency Management

Add this rule to `codex_rules_hypothe_x_ts.md` under implementation or verification rules.

## Dependency Management Rule

- Whenever a new library is introduced, Codex must add it to the correct dependency manifest in the same ticket.
- Backend Python libraries must be added to `backend/requirements.txt` immediately.
- Frontend JavaScript libraries must be added to `frontend/package.json` immediately.
- Codex must not import a library that is not declared in the project dependency files.
- If a library is optional or environment-specific, Codex must document why and where it is required.
- After dependency changes, Codex must run the relevant install command and verify that the project still starts.
- Do not leave dependency additions for later cleanup tickets.

Recommended companion rule:
- Keep dependency files minimal and remove unused dependencies when safely verified.
