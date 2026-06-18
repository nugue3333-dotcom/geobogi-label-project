# Testing Checklist

## Required before merge

- Unit tests pass.
- Integration tests pass where affected.
- Build succeeds.
- Lint/type checks pass if configured.
- No secret or `.env` file is included.
- No customer PII is logged.

## Barcode tests

- Barcode values preserve leading zeros.
- Numeric-looking barcodes are treated as strings.
- Supported barcode types render correctly.
- Unsupported barcode types fail with a clear error.
- Invalid barcode length fails safely.

## Label printer tests

- Label size conversion is correct.
- DPI conversion is correct.
- Print preview matches selected label size.
- Missing printer driver shows a useful error.
- Offline printer shows a useful error.
- USB, COM, network, or configured connection mode is not broken.

## Scanner tests

- Keyboard wedge input works.
- Enter/tab suffix handling works.
- Duplicate scans are handled according to configuration.
- Fast repeated scans do not corrupt input.
- Non-ASCII input does not crash the app.

## Inventory workflow tests

- Product lookup by barcode works.
- Unknown barcode path is clear.
- Inbound stock update is correct.
- Outbound stock update is correct.
- Stock cannot become negative unless configuration permits it.

## Marketing/content tests

- No unsupported model claim.
- No unsupported integration claim.
- No price/discount/warranty text change without approval.
- FAQ matches current software behavior.

## Release tests

- Migration tested on copy of data.
- Rollback path exists.
- Version number updated.
- Release notes drafted.
