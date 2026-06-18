# Codex Release Prep Prompt

Prepare a release candidate review. Do not deploy production.

Steps:

1. Read `docs/RELEASE_CHECKLIST.md`.
2. Inspect changed files since the last release tag or main branch.
3. Identify behavior changes, migrations, hardware impact, and marketing copy impact.
4. Draft release notes.
5. Identify rollback steps.
6. Identify required human approvals.

Output:

```md
## Release candidate summary

## Changed behavior

## Tests required

## Hardware impact

## Customer data impact

## Marketing/business impact

## Rollback plan

## Human approvals required

## Release notes draft
```
