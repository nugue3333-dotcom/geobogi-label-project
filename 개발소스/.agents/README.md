# 멀티 AI 에이전트 회의

이 폴더는 현재 프로젝트에서 Codex 작업을 여러 AI 에이전트의 회의형 워크플로로 진행하기 위한 로컬 구성이다. 기본 방식은 Codex 앱 내부 서브에이전트이며, 단순 병렬 실행이 아니라 `문제 진단 -> 해결안 토론 -> 합의안 구현 -> 검증과 출시 판단`을 역할별로 나눠 진행한다.

연결된 프로젝트 스킬:

```text
.agents/skills/multi-agent-orchestrator/
```

## 기본 실행: Codex 앱 내부 멀티 에이전트

PowerShell에서 `codex.exe`를 다시 실행하는 방식은 Windows 샌드박스, 한글 경로, 작업공간 권한 문제로 실제 수정이 누락될 수 있다. 일반 작업은 Codex 앱 대화창에서 요청한다.

```text
Codex 앱 멀티에이전트로 [수행할 작업] 진행해
```

앱 내부 역할:

- `project-mapper`: 영향 범위와 실행/검증 명령 확인
- `label-release-reviewer`: 고객용 EXE, dry-run, 출력 안전장치, 배포 위험 검토
- `feature-worker`: 지정된 좁은 범위 구현
- `qa-release-verifier`: 테스트, 빌드, dry-run, 고객 실행 표면 검증
- `lead-integrator`: 현재 Codex 앱 대화에서 통합, 충돌 조정, 최종 보고

완료 기준:

- 변경 파일과 고객용 실행폴더 반영 여부가 명확해야 한다.
- printer side effect가 있는 작업은 기본 dry-run으로 검증한다.
- 고객용 EXE가 영향을 받으면 테스트, PyInstaller 빌드, `고객용_실행폴더` 복사, 해시 확인, 실제 EXE smoke 검증을 모두 남긴다.
- 고객 배포가 포함되면 새 `고객배포` 폴더 또는 명시된 고객 전달 폴더까지 반영 여부와 경로를 기록한다.
- `고객환경점검.exe --base-dir .\고객용_실행폴더`를 실행해 `out\customer_preflight_report.txt`와 `out\customer_support_package.zip` 생성 여부를 확인한다.
- dry-run 후 `print_queue.xlsx`, `print_log.xlsx`, `last_run.log`, `out\` 산출물을 확인하고 실패/누락을 최종 보고에 적는다.
- `--print`, `02_print_labels.cmd`, `run_label_job.ps1 -Mode Print`는 사용자의 명시 요청 없이는 실행하지 않는다.
- 실제 프린터 전송 성공과 실제 라벨 출력 성공을 같은 의미로 보고하지 않는다.
- `templates/default_label.json`의 기본 템플릿은 계속 `"elements": []`인지 확인한다.
- 실제 프린터 출력, 스캐너 입력, 고객 PC 드라이버/USB/COM/LAN은 장비 검증 전까지 미확인 위험으로 기록한다.

## 레거시 보조 실행: 프롬프트/회의록 생성

프롬프트와 회의록만 생성:

```powershell
pwsh -NoProfile -ExecutionPolicy Bypass -File .\scripts\start_agent_council.ps1 -Task "수행할 작업을 여기에 적기"
```

생성 위치:

```text
.agents\councils\yyyyMMdd_HHmmss\
```

회의록:

```text
.agents\councils\yyyyMMdd_HHmmss\transcript.md
```

`-Launch`는 Codex CLI를 터미널에서 중첩 실행하는 레거시 방식이다. 사용자가 명시적으로 요청하지 않는 한 실제 수정 작업에는 사용하지 않는다.

## 레거시 보조 실행: 역할별 프롬프트 생성

```powershell
.\scripts\start_multi_agents.ps1 -Task "수행할 작업을 여기에 적기"
```

생성 위치:

```text
.agents\runs\yyyyMMdd_HHmmss\
```

역할별 독립 `-Launch` 실행도 레거시 방식이다. 서로 대화하지 않고 터미널에서 Codex CLI를 다시 실행하므로, 실제 수정이 필요한 작업에는 Codex 앱 내부 멀티에이전트를 사용한다.

