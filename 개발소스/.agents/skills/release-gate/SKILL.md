---
name: release-gate
description: Use before preparing or reviewing a release, deployment, version bump, production build, database migration, or customer-facing software update.
---

# Release Gate Skill

## Source of truth

- `docs/RELEASE_CHECKLIST.md`
- `docs/TESTING_CHECKLIST.md`
- `docs/SECURITY_GUARDRAILS.md`
- `docs/APPROVAL_MATRIX.md`

## Procedure

1. Identify changed files and behavior.
2. Classify release type: patch, minor, major.
3. Confirm tests and build commands were run.
4. Check hardware impact.
5. Check customer data impact.
6. Check marketing/business impact.
7. Draft release notes.
8. Identify rollback plan.
9. Block production deployment if required approvals are missing.

## Blockers

- Test failure
- Build failure
- No rollback path
- PII logging
- Secret exposure
- Database migration without approval
- Pricing/ad/warranty/refund change without approval
- Hardware compatibility claim without verification

## Output

```md
## Release gate result

Status: Pass / Blocked

## Evidence

## Blockers

## Required approvals

## Release notes draft

## Rollback plan
```
