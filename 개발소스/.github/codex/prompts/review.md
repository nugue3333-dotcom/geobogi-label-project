# Codex PR Review Prompt

Review this pull request for serious issues only.

Use the repository `AGENTS.md` and docs as review policy.

Focus areas:

1. Security and secret exposure
2. Customer data / PII logging
3. Barcode leading-zero handling
4. Label size and DPI conversion
5. Scanner input corruption
6. Printer connection failure handling
7. Unsupported hardware compatibility claims
8. Pricing, margin, refund, warranty, shipping, or ad budget changes
9. Missing tests for changed behavior
10. Production deployment risk

Output format:

```md
## Codex Review

### Blocking issues
- 

### High-risk issues
- 

### Tests missing
- 

### Safe to merge?
Yes/No, with reason.
```
