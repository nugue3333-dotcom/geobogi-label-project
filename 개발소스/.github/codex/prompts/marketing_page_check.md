# Codex Marketing Page Check Prompt

Review product page, ad copy, FAQ, or keyword changes.

Use `docs/MARKETING_AUTOMATION_RULES.md` and `docs/PRODUCT_PACKAGES.md` as source of truth.

Check for:

- Unsupported hardware compatibility claims
- Unsupported POS/ERP/e-commerce integration claims
- Wrong package components
- Wrong barcode type or label size
- Price/discount/warranty/refund/shipping change
- Exaggerated claims
- Missing limitation wording

Output:

```md
## Marketing copy review

### Approved claims
- 

### Risky or unsupported claims
- 

### Required corrections
- 

### Human approval needed
- None / Price / Warranty / Refund / Hardware / Integration / Ad budget
```
