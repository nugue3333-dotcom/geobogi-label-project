# Codex Barcode Automation MD Pack

바코드 프린터·스캐너 패키지 판매 사업에서 Codex가 코드 수정, 리뷰, 테스트, 배포 준비, 마케팅 문구 점검을 일관되게 수행하도록 만든 Markdown 파일 묶음이다.

## 배치 위치

- `AGENTS.md` → 저장소 루트에 둔다.
- `.agents/skills/*/SKILL.md` → Codex Skill로 사용한다.
- `.github/codex/prompts/*.md` → Codex GitHub Action의 `prompt-file`로 사용한다.
- `.github/ISSUE_TEMPLATE/*.md` → GitHub Issue 템플릿으로 사용한다.
- `docs/*.md` → Codex가 참고할 운영 기준 문서로 사용한다.

## 사용 원칙

1. 먼저 `AGENTS.md`의 설정/테스트/배포 명령을 실제 프로젝트에 맞게 수정한다.
2. 하드웨어 호환성, 가격, 광고비, 개인정보 관련 규칙은 임의로 삭제하지 않는다.
3. Codex 자동화는 PR 생성과 테스트까지 허용하고, 실서버 배포·가격 변경·광고비 증액은 승인제로 둔다.
4. 모든 자동 수정은 이슈, PR, 로그 중 하나와 연결되어야 한다.
