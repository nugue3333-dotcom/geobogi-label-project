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
   - Printer command references: `references/tsc/README.md`, `references/bixolon/README.md`, `references/zebra/README.md`
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
.\라벨출력엔진.exe --config .\config.ini --dry-run
.\고객용_실행폴더\라벨출력엔진.exe --config .\고객용_실행폴더\config.ini --dry-run
```

## Build Commands

```powershell
pwsh -NoProfile -ExecutionPolicy Bypass -File .\scripts\build_release_exes.ps1 -Version (Get-Date -Format "yyyy.MM.dd.HHmm") -TestResult "pytest: actual result"
```

The release script clean-builds all six specs, keeps only the Korean-named EXEs
in `dist\`, synchronizes them to the project root, `고객용_실행폴더`, and the
parent final folder, verifies SHA-256 equality, and regenerates the full customer
payload manifest. Do not run separate PyInstaller commands concurrently with it.

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

## Output-management regression memory

- The source tree is authoritative. Change `개발소스` first, then synchronize
  the customer runtime and deployment package from the verified source build.
- The operational baseline is the Korean-named EXE set directly under
  `the source root`. Never validate only `dist` or an
  older deployment folder. Rebuild all six EXEs, synchronize this baseline and
  the newest `고객배포` folder, then prove equality with SHA-256 hashes.
- The default `barcode_db.xlsx` is generated by
  `scripts/create_barcode_db.py`; keep the source root, `db`, and customer
  runtime copies aligned. It must remain a usable demo DB, not an empty file.
- Label-manager changes must preserve the contract: DB product name and price
  are left-aligned within the configured label, the barcode is centered, and
  text is selected to fit the physical label capacity instead of printing all
  database columns blindly.
- Data-source search filters the visible list immediately across every actual
  DB column. It must preserve the original rows and print selections, and
  clearing the query must restore the full list.
- Large-label auto layout uses the configured printable height: text starts at
  the printable top margin, the barcode remains centered and reaches the
  printable bottom, and a 100×100mm label must not contain a small centered
  content stack.
- On 80×80mm and larger labels, a 1D barcode must remain visually subordinate
  to the text block and its human-readable value must be clearly printed below
  the bars. Preserve the verified 100×100mm BIXOLON HRI sizing regression test.
- A handled designer transport failure must return the failed item to pending
  so the next explicit Print action can retry. Only an interrupted process with
  genuinely uncertain physical output may remain in the unknown state.
- A persisted unknown designer item must not permanently block later printing.
  When the user explicitly presses Print again, preserve confirmed sent items,
  recover stale unknown items to pending, and replace a stale different-job
  record with the new explicit print job.
- Any change to layout, DB-to-label mapping, or print progress requires focused
  template/manager regression tests before customer deployment. After copying,
  compare deployment hashes and run the customer preflight plus UI smoke tests.

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

<!-- MULTI_AGENT_COUNCIL_START -->
## Multi AI Agent Council

이 프로젝트의 기본 멀티 AI 에이전트 방식은 Codex 앱 내부 서브에이전트다. PowerShell에서 `codex.exe`를 다시 호출하는 방식은 Windows 샌드박스와 경로 문제로 실제 수정이 누락될 수 있으므로 일반 작업에는 사용하지 않는다.

기본 참여 에이전트: project-mapper, label-release-reviewer, feature-worker, qa-release-verifier, lead-integrator

사용자는 Codex 앱 대화창에서 다음처럼 요청한다.

```text
Codex 앱 멀티에이전트로 [작업 설명] 진행해
```

앱 내부 운영 규칙:

- lead-integrator는 현재 Codex 앱 대화가 맡고, 전체 범위 확정, 충돌 조정, 최종 검증과 보고를 책임진다.
- project-mapper는 읽기 전용 탐색으로 영향 파일, 실행 명령, 테스트 명령, 위험 지점을 찾는다.
- label-release-reviewer는 고객용 EXE, dry-run, 출력 안전장치, 고객 배포 폴더 위험을 검토한다.
- feature-worker는 lead-integrator가 지정한 좁은 파일 범위만 수정한다.
- qa-release-verifier는 테스트, 빌드, dry-run, 고객 실행 표면 검증을 맡는다.
- 여러 에이전트가 같은 파일을 동시에 수정하지 않도록 쓰기 범위를 분리한다.
- 외부 효과가 있는 작업은 명시 요청 전에는 dry-run, 정적 검증, 읽기 전용 검증으로 제한한다.

터미널 스크립트는 레거시 보조 도구다. 프롬프트/회의록 패키지가 필요할 때만 사용한다.

```powershell
pwsh -NoProfile -ExecutionPolicy Bypass -File .\scripts\start_agent_council.ps1 -Task "작업 설명"
```

`-Launch`는 Codex CLI를 터미널에서 중첩 실행하는 레거시 방식이며 기본적으로 차단된다. 명시적으로 승인된 진단에서만 `-Launch -AllowLegacyNestedLaunch`를 함께 지정할 수 있다. 실제 수정 작업은 Codex 앱 내부 서브에이전트를 사용한다. 회의 산출물은 `.agents/councils/`에 생성되며 Git 추적 대상에서 제외한다.
<!-- MULTI_AGENT_COUNCIL_END -->

## 라벨출력관리 인쇄 매수 계약

- 라벨출력관리의 인쇄 버튼은 인쇄 전에 항상 `인쇄 매수 선택` 창을 연다.
- 체크한 행이 있으면 선택한 각 항목에 같은 인쇄 매수를 적용하고, 체크한 행이 없으면 전체 항목에 적용한다.
- 선택 인쇄 또는 매수 재정의는 임시 출력 큐에만 반영하며 연결 DB와 기본 `print_queue.xlsx`의 저장값을 바꾸지 않는다.
- 인쇄 매수 선택을 취소하면 프린터 명령을 전송하지 않는다.
