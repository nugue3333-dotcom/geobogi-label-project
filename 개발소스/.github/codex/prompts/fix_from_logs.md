# Codex Fix From Logs Prompt

Use this prompt when an issue contains sanitized application logs.

Task:

1. Identify the failure category: printer, scanner, barcode, label, inventory, integration, UI, database, or deployment.
2. Find the smallest code path responsible.
3. Reproduce with a test if possible.
4. Fix the issue with the smallest safe patch.
5. Add regression tests.
6. Do not change pricing, ad, deployment, or customer-data handling.
7. Summarize the fix and residual risk.

Required output:

```md
## Diagnosis

## Files changed

## Tests added/updated

## Commands run

## Risk

## Human approval needed
```
