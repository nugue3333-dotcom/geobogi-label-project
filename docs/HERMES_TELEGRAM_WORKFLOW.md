# Hermes 및 Telegram 활용 흐름

## 목적

외부에 있을 때 Telegram으로 수정 방향이나 카피를 남기고, Codex가 로컬 프로젝트에 안전하게 반영하는 흐름을 만듭니다.

## 기본 흐름

1. Telegram 또는 Hermes에 수정 요청을 남깁니다.
2. 프로젝트 폴더에서 `ask-hermes.ps1`로 요청을 정리합니다.
3. 결과를 `.agent/hermes-last.md`에 저장합니다.
4. Codex가 `.agent/hermes-last.md`, `AGENTS.md`, `docs/PRODUCT_PACKAGES.md`, `docs/MARKETING_AUTOMATION_RULES.md`를 읽고 반영합니다.
5. 위험 문구, 가격, 보증, 환불, 배송, 외부 연동 주장은 승인 전 공개 문구에 넣지 않습니다.

## 현재 연결 확인

- 확인된 Telegram 대상: `telegram:7949317631`
- 표시 이름: `woo`
- Codex 안에서는 Hermes MCP의 `conversations_list`, `messages_read`, `messages_send`로 최근 대화를 확인하거나 답장을 보낼 수 있습니다.
- PowerShell에서는 `scripts/send-telegram-update.ps1`로 작업 결과를 보낼 수 있습니다.

## 실행 예시

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\ask-hermes.ps1 "바코드 프린터 + 스캐너 + 발행 프로그램 패키지 홈페이지의 CTA와 문의 섹션을 더 부드럽게 정리해줘."
```

Telegram으로 작업 결과를 보내려면 아래처럼 실행합니다.

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\send-telegram-update.ps1 -Message "홈페이지 1차 수정과 배포 ZIP 생성이 완료됐습니다."
```

파일 내용을 Telegram으로 보내려면 아래처럼 실행합니다.

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\send-telegram-update.ps1 -File .\docs\CUSTOMER_DISTRIBUTION.md -Subject "[거복이의꿈]"
```

외부에서 받은 수정 요청을 프로젝트 작업 파일로 저장하려면 아래처럼 실행합니다.

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\save-telegram-edit-request.ps1 "홈페이지 문의 섹션을 카카오톡 상담 중심으로 바꿔줘."
```

## Codex 반영 요청 예시

```text
.agent/hermes-last.md를 읽고 AGENTS.md와 PRODUCT_PACKAGES.md 기준으로 위험 문구를 줄여 index.html을 개선해줘.
```

Telegram 요청 파일을 반영하려면 이렇게 요청합니다.

```text
.agent/telegram-edit-request.md를 읽고 AGENTS.md와 PRODUCT_PACKAGES.md 기준으로 index.html 수정 계획을 먼저 보여줘.
```

## 주의

- 고객 개인정보, 주문 원문, 결제 정보, API 키는 Telegram이나 Hermes 요청에 넣지 않습니다.
- 가격, 할인, 보증, 환불, 배송비, 설치지원 조건은 사람이 승인한 문서가 생긴 뒤 공개 문구에 반영합니다.
- Hermes 답변은 초안이며, 최종 공개 문구는 프로젝트 문서 기준으로 다시 점검합니다.
