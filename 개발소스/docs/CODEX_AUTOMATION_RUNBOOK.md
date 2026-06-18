# Codex Automation Runbook

## Purpose

Codex should automate repeatable development and review tasks while staying inside strict business, security, and release boundaries.

## Automation levels

### Level 1: Analysis only

Codex reads logs, issues, and files, then produces a diagnosis. No code is changed.

Allowed:
- Error classification
- Root-cause hypothesis
- Test gap identification
- Marketing copy risk review

### Level 2: Pull request creation

Codex edits code, adds tests, and opens a PR. No production deployment.

Allowed:
- Bug fix PR
- Test PR
- Documentation PR
- Safe refactor PR

### Level 3: CI automation

Codex runs through GitHub Actions using a committed prompt file.

Allowed:
- PR review
- Release note draft
- Failing test repair proposal
- Dependency update review

### Level 4: Restricted execution

Codex can update low-risk text or config after tests pass.

Allowed:
- FAQ correction
- Non-financial product copy cleanup
- Internal documentation update

### Level 5: Human approval required

Never fully automate these:

- Production release
- Price change
- Discount change
- Ad budget increase
- Warranty/refund policy change
- New hardware compatibility claim
- Customer data export
- Payment/order integration change

## Daily job flow

1. Collect errors, failed jobs, customer support tags, and sales/marketing metrics.
2. Create issues for software defects and documentation gaps.
3. Run Codex against high-priority issues.
4. Require tests for changed behavior.
5. Request human approval for release, pricing, ad budget, or marketing claims.
6. Merge only after CI passes.
7. Record result in `docs/AUTOMATION_DECISION_LOG.md`.

## Incident stop conditions

Stop automation immediately when any of these occur:

- Unexpected deletion or migration of customer data
- Repeated failed releases
- Sudden increase in refund, return, or support tickets
- Ad spend anomaly
- Secret/token exposure
- Printer output defects affecting real labels
- Scanner input corruption
