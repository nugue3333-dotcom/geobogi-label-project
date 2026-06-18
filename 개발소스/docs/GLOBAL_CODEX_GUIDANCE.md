# Global Codex Guidance

Use this as `~/.codex/AGENTS.md` when working across many repositories.

## Working agreements

- Prefer minimal patches.
- Before changing behavior, identify the existing behavior and the intended behavior.
- Always run the closest relevant test after editing code.
- Never commit secrets, tokens, credentials, or `.env` files.
- Ask for approval before adding production dependencies, changing deployment settings, changing pricing logic, or changing customer-data handling.
- Summaries must include changed files, tests run, and remaining risks.

## Default review focus

- Security regression
- Data loss
- Silent failure
- Incorrect financial calculation
- Broken test coverage
- Over-broad code changes
- Unclear rollback path
