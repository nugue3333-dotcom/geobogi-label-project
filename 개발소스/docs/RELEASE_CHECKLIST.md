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

## Automated EXE and manifest gate

Run the repository tests first, then pass the real test summary to the single release command:

```powershell
pwsh -NoProfile -ExecutionPolicy Bypass -File .\scripts\build_release_exes.ps1 -Version (Get-Date -Format "yyyy.MM.dd.HHmm") -TestResult "pytest: actual passing result"
```

- [ ] All six specs clean-built: `customer_preflight`, `label_designer`, `label_job_runner`, `label_manager`, `print_labels`, `printer_settings`
- [ ] `dist\` contains only `고객환경점검.exe`, `라벨디자이너.exe`, `라벨작업실행기.exe`, `라벨출력관리.exe`, `라벨출력엔진.exe`, `프린터설정.exe`
- [ ] EXE SHA-256 values match in the source root, `고객용_실행폴더`, and the parent final folder
- [ ] `release_manifest.json` validator reports no missing, changed, unexpected, or forbidden files
- [ ] Manifest build metadata contains all six spec hashes, Python/PyInstaller versions, build ID, package version, and the real test result
- [ ] Runtime output (`out\`, `_backup\`, logs, support ZIP, PyInstaller `_MEI*`) is not recorded as release payload

## Hardware verification

- [ ] Printer model checked
- [ ] Scanner model checked
- [ ] Label size checked
- [ ] Barcode type checked
- [ ] Driver/connection mode checked

## Paid-product workflow gate

- [ ] GS1 selected-row edits are applied or explicitly rejected before validation/apply; cancel preserves the source
- [ ] Designer → repeating print retains the saved template, DB sheet/fields, media and options; unsaved work is handled explicitly
- [ ] User-template printing and automatic default layout are visibly distinguished
- [ ] Missing/moved/changed DB source and invalid rows have actionable messages
- [ ] Generated serial/date values are fixed for the confirmed job; preview does not consume numbers; uncertain transmission is not retried automatically
- [ ] Current manual screenshots and source/module hashes match; all PDF/DOCX/text copies have the release version
- [ ] Customer starts through `시작하기.cmd`; root OCR helper EXEs are excluded, `tools/ocr` runtime is preserved
- [ ] Previous customer folders and config/DB/queue data are preserved; rollback and recovery instructions are available
- [ ] Customer migration evidence uses `TEMPLATE_MIGRATION_CHECKLIST.md`; empty forms are not recorded as completed work
- [ ] Physical device evidence uses `DEVICE_ACCEPTANCE_RECORD.md`; empty forms do not authorize model compatibility claims
- [ ] Pricing/license/support terms in `PAID_SUPPORT_TERMS_DRAFT.md` are approved before offering those terms to a customer

Automated build, manifest, dry-run and command decoding can pass while physical
device approval and commercial terms remain pending. Record the two outcomes
separately; do not turn a prepared form into a hardware or customer acceptance.

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
