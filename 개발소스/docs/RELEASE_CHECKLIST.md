# Release Checklist

## Release type

- [ ] Patch: bug fix only
- [ ] Minor: new feature, backward compatible
- [ ] Major: breaking behavior or migration

## Required evidence

- [ ] Linked issue or task exists
- [ ] Tests passed
- [ ] Build passed
- [ ] Regression risk reviewed
- [ ] Customer data handling unchanged or reviewed
- [ ] Device compatibility unchanged or reviewed
- [ ] Marketing copy unchanged or reviewed
- [ ] Rollback path documented

## Hardware verification

- [ ] Printer model checked
- [ ] Scanner model checked
- [ ] Label size checked
- [ ] Barcode type checked
- [ ] Driver/connection mode checked

## Business approval required when affected

- [ ] Price
- [ ] Discount
- [ ] Shipping fee
- [ ] Warranty
- [ ] Refund policy
- [ ] Ad budget
- [ ] Product package composition
- [ ] Hardware compatibility claim

## Release notes format

```md
## Version

## Changed

## Fixed

## Known issues

## Upgrade notes

## Rollback
```

## Post-release monitoring

Track for 24 hours:

- New error count
- Setup failure tickets
- Printer failure tickets
- Scanner failure tickets
- Refund/return requests
- Ad conversion drop
- Order processing failure
