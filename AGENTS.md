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

- The default customer DB is a sales demo, not an internal work sheet: keep
  only `barcode`, `item_code`, `item_name`, and `판매가`. Do not reintroduce
  `lot_no`, `qty`, or `print_qty`; queue conversion supplies its private
  defaults.
- Customer prices must render as `4,600원`, never with the Unicode won glyph
  (`₩`), because printer and font paths can render that glyph incorrectly.
- Regression layout contract: product name, price, product code, centered
  barcode, and human-readable code must all remain inside the configured
  printable label area. Update the boundary test when layout rules change.
- The label designer data-source dialog must search by item name, select and
  scroll to the matching row, and retain that behavior after a DB reload.
- When label management connects a different DB, that DB becomes the only
  active print source. Never retain rows, columns, selections, or a selected
  print queue from the previous DB. Preserve every real DB column in the print
  queue and recalculate text-line and barcode layout from the current printer
  label size.

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
# 제품 목적

이 프로젝트는 라벨 바코드 발행 프로그램과 제품 판매 홈페이지를 구축하기 위한 프로젝트다.

최종 사업 모델은 다음 제품을 패키지로 온라인 판매하는 것이다.

- 라벨 바코드 발행 프로그램
- 바코드 프린터
- 바코드 스캐너
- 설치 및 초기 설정 지원
- 장비별 소모품과 추가 옵션

주요 사용자는 개발자가 아니라 매장, 창고, 제조 현장, 물류 현장에서 일하는 관리자와 작업자다.

제품의 핵심 가치는 다음과 같다.

1. 설치와 장비 연결이 쉽다.
2. 라벨을 빠르게 만들 수 있다.
3. 출력 크기와 위치가 정확하다.
4. 스캔과 출력 과정에서 실수가 적다.
5. 문제가 발생했을 때 원인을 쉽게 파악할 수 있다.

# 개발 우선순위

다음 순서로 완성한다.

1. 프로그램 실행과 기본 설정
2. 프린터 및 스캐너 연결 상태 확인
3. 라벨 템플릿 생성, 편집, 저장
4. 바코드 생성과 데이터 검증
5. 실제 크기 기반 출력 미리보기
6. 테스트 출력과 실제 출력
7. 스캔 입력 처리
8. 출력 기록과 오류 기록
9. 템플릿 가져오기와 내보내기
10. 설치 프로그램과 업데이트 기능
11. 제품 판매 홈페이지와 고객 지원 기능

핵심 흐름을 먼저 완성하고 사용 빈도가 낮은 고급 기능은 뒤로 미룬다.

# 하드웨어 연동 원칙

- 특정 프린터나 스캐너 SDK를 UI 또는 도메인 코드에서 직접 호출하지 않는다.
- 프린터, 스캐너, 통신 방식별 어댑터 인터페이스를 사용한다.
- Windows 드라이버 출력, USB, 시리얼, 네트워크, 키보드 입력 방식이 서로 분리되도록 설계한다.
- 지원 장비 모델과 명령어는 반드시 제조사 공식 문서로 검증한다.
- 프린터 언어와 장비 기능을 추측하지 않는다.
- ZPL, TSPL, EPL 등 장비별 명령은 독립된 드라이버 모듈로 분리한다.
- 실제 장비가 없어도 개발과 테스트가 가능하도록 프린터 및 스캐너 시뮬레이터 또는 mock 모드를 제공한다.
- mock 모드는 실제 성공처럼 가장하지 않고 화면에 명확히 표시한다.
- 전송 성공, 프린터 수신 성공, 물리적 출력 완료를 같은 상태로 취급하지 않는다.
- 장비가 제공하는 상태 조회 범위 안에서만 출력 성공 여부를 판단한다.
- 중복 출력 방지를 위해 출력 작업 ID와 실행 상태를 관리한다.
- 실패한 출력은 원인, 장비, 템플릿, 요청 시각, 재시도 여부를 기록한다.

# 라벨 정확도

- 라벨 크기는 mm 단위를 기준으로 관리한다.
- 화면 좌표, 프린터 DPI, 인쇄 좌표 간 변환을 한 곳에서 처리한다.
- 203 DPI, 300 DPI 등 해상도 차이를 고려한다.
- 반올림과 좌표 변환 규칙을 테스트로 고정한다.
- 라벨 폭, 높이, 여백, 간격, 회전, 인쇄 방향을 명시적으로 관리한다.
- 바코드의 최소 크기, 여백, 데이터 길이, 체크 문자 조건을 검증한다.
- 바코드가 생성되더라도 실제 스캔 가능성이 낮으면 경고한다.
- 출력 전 실제 크기 미리보기를 제공한다.
- 테스트 출력에는 위치와 크기를 확인할 수 있는 눈금 또는 기준선을 선택적으로 제공한다.

# 스캐너 입력

- 일반적인 키보드 웨지 방식의 스캐너 입력을 안정적으로 처리한다.
- 빠른 연속 입력과 사람이 직접 타이핑한 입력을 구분할 수 있도록 시간 간격과 종료 문자를 처리한다.
- 접두사, 접미사, Enter, Tab, CR, LF 설정을 지원 가능한 구조로 만든다.
- 동일 바코드의 우발적 연속 스캔을 제어할 수 있게 한다.
- 잘못된 데이터, 미등록 데이터, 중복 데이터 상태를 명확히 표시한다.
- 스캔 중에는 현재 입력 대상 필드가 명확해야 한다.

# 프로그램 UI

프로그램의 기본 정보 구조는 다음 흐름을 중심으로 설계한다.

1. 장비 설정
2. 라벨 템플릿
3. 데이터 입력 또는 가져오기
4. 출력 미리보기
5. 출력 실행
6. 출력 결과 확인

다음 UI 원칙을 적용한다.

- 첫 실행 시 장비 연결과 테스트 출력을 안내하는 설정 마법사를 제공한다.
- 현재 연결된 프린터와 스캐너 상태를 항상 확인할 수 있게 한다.
- 라벨 편집기는 캔버스, 요소 목록, 속성 패널, 미리보기 영역을 명확히 구분한다.
- 자주 사용하는 작업은 한두 번의 클릭으로 실행할 수 있게 한다.
- 고급 프린터 설정은 기본 화면에 모두 노출하지 않고 단계적으로 표시한다.
- 삭제, 대량 출력, 템플릿 덮어쓰기 전에는 영향 범위를 명확히 표시한다.
- 저장되지 않은 변경사항을 잃지 않도록 보호한다.
- 사용자가 이해하기 어려운 장비 코드나 프로토콜 메시지는 쉬운 한국어 오류로 변환하고 상세정보를 별도로 제공한다.
- 버튼 이름은 “확인”, “실행”처럼 모호하게 작성하지 말고 “테스트 라벨 출력”, “템플릿 저장”처럼 행동을 구체적으로 표현한다.

# 판매 홈페이지

홈페이지의 목적은 방문자가 패키지 구성을 이해하고 구매 또는 상담까지 진행하게 만드는 것이다.

필수 페이지 또는 영역은 다음과 같다.

- 메인 제품 소개
- 프로그램 주요 기능
- 실제 사용 흐름
- 프린터 및 스캐너 패키지 구성
- 지원 장비와 소모품 호환표
- 업종별 활용 사례
- 가격 또는 견적 요청
- 프로그램 화면과 출력 결과 예시
- 설치 및 초기 설정 안내
- 다운로드와 업데이트
- 자주 묻는 질문
- 고객 지원과 문의
- 개인정보 처리방침과 이용약관

홈페이지 구현 원칙은 다음과 같다.

- 프로그램과 홈페이지가 동일한 브랜드 색상, 로고, 타이포그래피, 컴포넌트 규칙을 사용하게 한다.
- 추상적인 홍보 문구보다 실제 기능, 지원 장비, 출력 예시, 설치 과정, 제한사항을 보여준다.
- 장비 호환 여부를 고객이 구매 전에 확인할 수 있게 한다.
- 모바일에서도 제품 구성과 구매 흐름이 깨지지 않아야 한다.
- 검색엔진이 제품명, 장비명, 바코드 프린터, 라벨 발행 프로그램 관련 내용을 이해할 수 있도록 시맨틱 HTML과 메타데이터를 사용한다.
- 이미지 최적화, 지연 로딩, 번들 크기 관리를 적용한다.
- 존재하지 않는 후기, 고객사, 인증, 지원 장비를 만들어내지 않는다.

# 완료 기준

기능 개발은 최소한 다음 시나리오가 처음부터 끝까지 동작해야 완료된 것으로 판단한다.

1. 프로그램 실행
2. 프린터와 스캐너 설정
3. 라벨 크기 선택
4. 텍스트와 바코드 배치
5. 데이터 입력
6. 실제 크기 미리보기
7. 테스트 출력
8. 실제 출력 요청
9. 출력 결과와 오류 기록 확인
10. 바코드 스캔과 데이터 확인

실제 장비가 없는 환경에서는 mock 장비로 자동 테스트하고, 실제 장비에서 확인하지 못한 사항을 별도로 기록한다.
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
