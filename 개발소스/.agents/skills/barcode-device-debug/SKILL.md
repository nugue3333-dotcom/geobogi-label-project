---
name: barcode-device-debug
description: Use when debugging barcode printer, barcode scanner, label size, DPI, barcode encoding, USB/COM/network connection, or inventory scan problems.
---

# Barcode Device Debug Skill

## Trigger examples

Use this skill for:

- Printer offline or driver failure
- Wrong label size
- Blurry or misaligned barcode
- Barcode leading zero removed
- Scanner input duplicated or missing suffix
- COM/USB/network connection issue
- QR/DataMatrix/Code128/EAN-13 rendering issue

## Procedure

1. Identify device type: printer, scanner, or software-only.
2. Identify connection mode: USB, COM, network, keyboard wedge, HID, or unknown.
3. Preserve barcode values as strings.
4. Check label units and DPI conversion.
5. Add a regression test before or with the fix.
6. Keep user-facing error messages actionable.
7. Do not add unsupported model compatibility claims.
8. Do not log customer information.

## Required checks

- Leading zeros preserved
- Label size conversion tested
- Unsupported barcode type fails safely
- Missing printer/scanner gives clear error
- Fast repeated scanner input does not corrupt data

## Output

```md
## Device diagnosis

## Root cause

## Fix

## Regression tests

## Remaining risk
```
