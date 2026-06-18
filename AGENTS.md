# AGENTS.md

## Project Context

This repository supports the "Geobogi Dream" barcode label printing package:
barcode printers, scanners, label design, Excel-driven print queues, customer
deployment folders, printer settings, and the mobile Android label-printing app.

Primary goal: keep label printing, barcode scanning, DB lookup, and customer
setup reliable for non-technical customers immediately after installation.

## Non-Negotiable Rules

- The MVP defaults to dry-run behavior. Actual printer output must only happen
  through an explicit `--print` path plus confirmation where the CLI requires it.
- Keep printer transports separate from label rendering so templates can be
  tested without network, USB, driver, or OS dependencies.
- Do not remove validation around barcode length, barcode type, printer DPI,
  label size, encoding, USB/COM/network printer connection, or scanner input
  mode.
- Barcode validation must preserve leading zeros. Treat barcode values as
  strings, not numbers.
- Do not log payment data, resident registration numbers, raw access tokens,
  API keys, customer phone numbers, customer addresses, or full order payloads.
- Do not commit `.env`, secrets, API keys, vendor credentials, store tokens, ad
  platform tokens, or local customer data.
- Do not add unsupported hardware compatibility claims. Only mention
  printer/scanner models that are listed in `docs/PRODUCT_PACKAGES.md` or
  confirmed in code/config.
- Do not change production pricing, margin logic, ad budget limits, or
  settlement calculations unless the issue explicitly requests it and the
  change is covered by tests.
- Do not make automatic production deployment changes. Production release
  requires the checklist in `docs/RELEASE_CHECKLIST.md`.
- Do not bypass tests to make a build pass.

## Expected Workflow

1. Read the issue, logs, failing test, or prompt completely.
2. Locate the smallest affected area.
3. Check relevant docs:
   - Device behavior: `docs/PRODUCT_PACKAGES.md`
   - Marketing copy: `docs/MARKETING_AUTOMATION_RULES.md`
   - Data and metrics: `docs/DATA_SCHEMA.md`
   - Release: `docs/RELEASE_CHECKLIST.md`
   - Security: `docs/SECURITY_GUARDRAILS.md`
   - Testing: `docs/TESTING_CHECKLIST.md`
4. Make the smallest safe change.
5. Add or update tests where behavior changes.
6. Run the closest relevant tests.
7. If customer-facing executables are affected, rebuild and copy them into
   `고객용_실행폴더`.
8. Summarize what changed, what was tested, and what still needs human approval.

## Setup Commands

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

Use the project venv when it exists. If the Windows temp/cache path causes
pytest permission problems, use repo-local temp/cache paths.

## Test Commands

```powershell
.\.venv\Scripts\python.exe -m pytest --basetemp .\pytest_tmp -p no:cacheprovider
.\.venv\Scripts\python.exe -m py_compile barcode_label_automation\label_manager_app.py
```

For print-engine smoke checks:

```powershell
.\print_labels.exe --config .\config.ini --dry-run
.\고객용_실행폴더\print_labels.exe --config .\고객용_실행폴더\config.ini --dry-run
```

## Build Commands

```powershell
.\.venv\Scripts\python.exe -m PyInstaller --clean --noconfirm .\print_labels.spec
.\.venv\Scripts\python.exe -m PyInstaller --clean --noconfirm .\printer_settings.spec
.\.venv\Scripts\python.exe -m PyInstaller --clean --noconfirm .\label_manager.spec
.\.venv\Scripts\python.exe -m PyInstaller --clean --noconfirm .\label_designer.spec
```

After rebuilding, copy the matching executables from `dist\` to the project root
and to `고객용_실행폴더` when those customer-facing files are part of the change.

## Code Style

- Prefer small, explicit functions over hidden side effects.
- Keep hardware-specific logic isolated by vendor/model/driver.
- Keep business rules in configuration or clearly named constants.
- Use defensive error messages for device failures: connection failure,
  unsupported DPI, missing driver, wrong label size, scanner keyboard mode, and
  scanner serial mode.
- Avoid broad exception swallowing. Log safe error codes, not customer data.
- Prefer focused pytest coverage for Excel validation, sanitization, scanner
  lookup, command rendering, and customer deployment behavior.

## Barcode Domain Rules

- Preserve leading zeros and numeric-looking barcode strings.
- Do not trim internal spaces unless the barcode standard or configuration
  requires it.
- Label dimensions must be handled in explicit units: mm, inch, px, or dots.
- Printer DPI conversion must be tested when changed.
- Scanner input may arrive as keyboard wedge, serial COM, USB HID, network
  input, or Android/PDA handoff. Do not assume only one mode.
- Add regression tests for printer/scanner bugs.

## Marketing Automation Rules

- Product page, ad copy, keyword, FAQ, and package copy must follow
  `docs/MARKETING_AUTOMATION_RULES.md`.
- Copy must sell the business outcome: label printing, stock control, faster
  receiving/shipping, and fewer manual errors.
- Copy must not promise unsupported POS/ERP/e-commerce integrations.
- Any change that affects price, discount, warranty, refund, shipping, hardware
  compatibility, integration, or ad budget requires human approval.

## Review Guidelines

Flag as high priority:

- New leakage of secrets or customer data.
- Broken barcode leading-zero handling.
- Incorrect label size or DPI conversion.
- Unverified hardware compatibility claims.
- Price, margin, shipping fee, or ad budget changes without approval.
- Production deployment without release checklist evidence.
- Removal of tests around printer/scanner behavior.

## Pull Request Summary Format

```md
## Summary
- 

## Tests
- 

## Risk
- Low/Medium/High

## Human approval needed
- None / Pricing / Production release / Marketing claim / Hardware compatibility
```
