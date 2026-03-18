---
agent: agent
description: Deploy the Taekwondo Competition Manager to AWS Lambda using Zappa
argument-hint: environment (optional, defaults to "dev")
tools: [execute, read/readFile, search/codebase]
---

Deploy this repository to Zappa for the environment `${input:environment:dev}`.

Follow this exact process:

1. Validate that `zappa_settings.json` contains the requested environment.
2. Determine and confirm the expected AWS account and profile before deployment:
   - Read `zappa_settings.json` for the selected environment and note any `profile_name` and, if available, an explicit `aws_account_id` or account IDs implied by resource ARNs (for example, `certificate_arn`, `s3_bucket`, or other ARNs).
   - Use `aws sts get-caller-identity` to obtain the active AWS `Account` ID and determine the currently active AWS profile (for example, from the AWS CLI configuration or environment).
   - If `profile_name` is set for the environment, treat that as the expected profile and compare it with the active profile.
   - If an expected account ID can be derived (explicit `aws_account_id` or from ARNs), treat that as the expected account and compare it with the `Account` from `aws sts get-caller-identity`.
   - If the active profile and/or account ID do not match the expected values, stop and ask the user in this chat to confirm before proceeding with any deployment commands, explicitly stating the expected vs. actual profile/account.
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