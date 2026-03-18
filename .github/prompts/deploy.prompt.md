---
agent: agent
description: Deploy the Taekwondo Competition Manager to AWS Lambda using Zappa
argument-hint : environment (optional, defaults to "dev")
tools: [execute, read/readFile, search/codebase]
---

Deploy this repository to Zappa for the environment `${input:environment:dev}`.

Follow this exact process:

1. Validate that `zappa_settings.json` contains the requested environment.
2. Confirm the active AWS identity and profile before deployment. Stop and ask for user confirmation if the active AWS profile does not match the expected deployment account.
3. Install and sync dependencies with `uv sync`.
4. Run tests with `uv run pytest` and stop if tests fail.
5. Upload secrets for the target environment with:
   - `uv run scripts/update_secrets.py --env <environment>`
6. Check whether the Zappa environment already exists:
   - If it exists, run `uv run zappa update <environment>`.
   - If it does not exist, run `uv run zappa deploy <environment>`.
7. After deploy/update, run `uv run zappa status <environment>`.
8. If deployment fails, run `uv run zappa tail <environment> --http` and summarize the most relevant errors.

Constraints:

- Default to `dev` unless a different environment is explicitly requested.
- Never deploy to `prod` without explicit user confirmation in this chat.
- Do not modify application code as part of deployment unless the user asks for a fix.
- Keep terminal output concise and summarize key results.

Return format:

- Environment:
- Action taken (`deploy` or `update`):
- Tests:
- Secrets upload:
- Zappa status summary:
- URL/domain:
- Any follow-up actions required: