---
name: marketing-automation-review
description: Use when reviewing or editing product pages, ad copy, keywords, FAQ, package descriptions, or marketing claims for barcode printer/scanner packages.
---

# Marketing Automation Review Skill

## Source of truth

- `docs/MARKETING_AUTOMATION_RULES.md`
- `docs/PRODUCT_PACKAGES.md`
- `docs/APPROVAL_MATRIX.md`

## Procedure

1. Extract every claim from the copy.
2. Classify each claim: package component, hardware model, feature, integration, price, warranty, refund, shipping, support, result claim.
3. Verify package/model/feature claims against source-of-truth docs.
4. Mark unsupported claims for removal.
5. Keep copy focused on operational value, not hype.
6. Require human approval for price, discount, warranty, refund, shipping, hardware compatibility, integration, or ad budget changes.

## Approved copy structure

```text
Customer problem → package solution → included components → supported conditions/limits → action-neutral closing
```

## Output

```md
## Copy review result

### Safe claims

### Unsupported claims

### Required edits

### Approval required
```
