# Product Packages

Use this document as the source of truth for package composition and marketing claims.

## Package table

| package_id | Public name | Printer | Scanner | Software | Supported labels | Supported barcodes | Status |
|---|---|---|---|---|---|---|---|
| starter-1d | 입문형 1D 바코드 패키지 | TBD | TBD | Basic label + inventory | TBD | Code128, EAN-13, Code39 | draft |
| warehouse-2d | 물류형 2D 바코드 패키지 | TBD | TBD | Inbound/outbound + label | TBD | Code128, QR, DataMatrix | draft |
| store-basic | 매장형 스캔 조회 패키지 | Optional | TBD | Product lookup + stock | TBD | Code128, EAN-13 | draft |

## Required before public claim

For each package, confirm:

- Printer model
- Scanner model
- Label width/height
- Barcode types
- Driver requirement
- OS support
- Connection method
- Software feature set
- Installation support terms
- Warranty/refund terms

## Approved printer models

This table is the release gate for public model names and model-specific runtime
allowlists. A manufacturer command manual alone does not approve a model.

| Manufacturer | Approved model | Command language | Physical output evidence | Approved post-processing | Public claim status |
|---|---|---|---|---|---|
| BIXOLON | None | SLCS renderer documented | None recorded | None approved by model | 상담 후 모델별 확인 |
| TSC | None | TSPL renderer documented | None recorded | None approved by model | 상담 후 모델별 확인 |
| Zebra | None | ZPL renderer documented | None recorded | None approved by model | 상담 후 모델별 확인 |
| SEWOO | None | Conditional ZPL adapter only | None recorded | `tear_off` only after model approval | 상담 후 모델별 확인 |

No printer model is currently approved for a concrete public compatibility
claim. Existing renderer tests verify command generation, not physical hardware
compatibility.

### Model approval procedure

1. Record the exact manufacturer and model.
2. Store the official command manual and index its file, hash, and relevant
   pages in `references/manufacturer-docs.md`.
3. Verify the required DPI, label dimensions, media sensor, connection method,
   barcode types, encoding, and requested post-processing on the physical model.
4. Record the evidence and change the model row from `None` to the exact model.
5. For SEWOO, add the exact same model to
   `APPROVED_SEWOO_ZPL_MODELS` in `barcode_label_automation/config.py`.
6. Run the focused configuration, settings, renderer, and customer dry-run
   tests before release approval.

SEWOO `cutter` and `peeler` remain blocked even after ZPL model approval until
separate model-specific manufacturer evidence and physical checks are approved.

## Claim rule

Codex must not add a package, model, label size, barcode type, integration, OS, or support promise to public copy unless it appears here or in a reviewed configuration file.

For BIXOLON, TSC, Zebra, and SEWOO, public copy must use
`상담 후 모델별 확인` while the approved-model table has no exact approved
entry. Do not use concrete model names, `완전 호환`, all-model support, or an
equivalent broad claim before approval.
