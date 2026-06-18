# Approval Matrix

## Automatic allowed

| Change | Allowed automatically | Condition |
|---|---:|---|
| Unit test update | Yes | Behavior change covered |
| Bug fix PR | Yes | Tests pass |
| Internal docs | Yes | No policy change |
| Error message improvement | Yes | No PII exposure |
| FAQ wording correction | Yes | No price/warranty/refund claim |

## Human approval required

| Change | Approval required |
|---|---|
| Production deployment | Always |
| Price change | Always |
| Discount change | Always |
| Ad budget increase | Always |
| Refund/warranty/shipping policy | Always |
| New hardware compatibility claim | Always |
| New external integration claim | Always |
| Customer data export | Always |
| Database migration on production | Always |
| New production dependency | Required unless explicitly pre-approved |

## Block automatically

| Condition | Action |
|---|---|
| Secret detected | Block PR/merge |
| Test failure | Block merge |
| Margin below minimum | Block change |
| Unsupported hardware claim | Block content change |
| PII logging introduced | Block PR/merge |
| Production deploy without checklist | Block deploy |
