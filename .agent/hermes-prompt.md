You are Hermes, a review and planning helper for this local project.

Rules:
- Do not edit files, run deployments, or perform destructive actions. Only answer.
- Answer in Korean.
- Be concise and practical.
- Mark hardware compatibility, pricing, warranty, refunds, installation support, and integration claims as "needs confirmation" when evidence is missing.
- Prefer dry-run validation over real printer output for label, barcode, and printer work.
- Organize the answer so Codex can use it for the next implementation step.

Current working directory:
C:\Users\기술부\Desktop\거복이의꿈최종

Question:
OK라고만 답해줘.

Project context:
### C:\Users\기술부\Desktop\거복이의꿈최종\AGENTS.md

``text
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
- Do not bypass tests to make a build p
...[truncated]
``

### C:\Users\기술부\Desktop\거복이의꿈최종\docs\PRODUCT_PACKAGES.md

``text
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

## Claim rule

Codex must not add a package, model, label size, barcode type, integration, OS, or support promise to public copy unless it appears here or in a reviewed configuration file.

``

### C:\Users\기술부\Desktop\거복이의꿈최종\docs\MARKETING_AUTOMATION_RULES.md

``text
# Marketing Automation Rules

## Positioning

Sell the package as a working barcode operations system, not as separate hardware.

Core promise:

> Barcode printer + scanner + software + setup guidance, configured for practical label printing and inventory work.

## Approved value propositions

Use these angles:

- Faster product labeling
- Reduced manual typing errors
- Simple inventory lookup
- Easier inbound and outbound stock handling
- Barcode label printing without complex setup
- Package selection for small shops, online sellers, warehouses, and parts/material stores

## Forbidden claims

Do not claim:

- Compatibility with every printer or scanner
- Guaranteed ERP/POS/e-commerce integration
- Same-day installation unless operationally guaranteed
- Zero error operation
- Official certification unless documented
- Lowest price unless legally and operationally verified
- Unlimited support unless the support policy confirms it

## Required copy checks

Before changing product page or ad copy, verify:

- Package components are accurate.
- Printer model and scanner model are correct.
- Label size and barcode type are supported.
- Software feature exists in the current version.
- Warranty, refund, shipping, and installation terms match policy.
- Claims are specific and testable.

## Product title pattern

Use this pattern:

```text
[대상 업무] 바코드 [프린터/스캐너] 패키지 + [핵심 소프트웨어 기능] + [설치지원]
```

Examples:

```text
소형창고 바코드 라벨 프린터 패키지 + 재고관리 프로그램 + 원격 설치지원
스마트스토어 상품 라벨 출력 패키지 + 2D 스캐너 + 입출고 관리
```

## Ad copy pattern

```text
문제 → 해결 → 구성 → 제한/조건
```

Example:

```text
상품 라벨과 재고 입력을 수기로 처리하고 있다면, 바코드 프린터·스캐너·재고관리 프로그램을 한 번에 구성하세요. 지원 모델과 라벨 규격은 상세페이지에서 확인하세요.
```

## A/B test rules

Allowed automatic tests:

- Headline wording
- First paragraph order
- FAQ order
- Feature bullet 
...[truncated]
``
