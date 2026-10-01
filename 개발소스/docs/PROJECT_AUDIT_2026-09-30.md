# 프로젝트 전체 점검·정리 — 2026-09-30

## 완료 결과

범위는 `거복이의꿈최종` 전체이며 Windows 정본 소스는 `개발소스`다.
Git 이력 내부를 제외한 같은 방식의 파일 용량 비교: 18,778,389,731 → 14,777,220,860바이트.
새 배포본과 보관용 압축파일을 포함하고도 4,001,168,871바이트(약 4.0GB)를 확보했다.

- 재생성 가능한 pytest 임시 파일, Python 캐시, 과거 PyInstaller 빌드 중간 파일 정리.
- 정리 계획 중 124개 경로 삭제 완료, 20개 경로는 권한 문제로 보존. 별도로 `.tmp` 전체와 고객 백업이 있는 `tmp/audit_*` 3개 경로를 보존했다.
- 과거 고객배포 `_archive_20260922`는 모든 2,906개 파일을 `고객배포/_archive_20260922.tar.gz`로 보관했다. 각 압축 항목의 SHA-256과 보관 직전 원본을 전수 대조한 후 원래 보관 폴더를 정리했다.
- 원본 과거 보관 폴더 10,305,639,687바이트 → 압축파일 6,958,359,637바이트. 같은 파일 내용은 표준 tar 하드링크 항목으로 저장했다.
- 과거 ZIP과 풀린 폴더 중 내용이 다른 사본도 모두 보관했다. 복구 시 사본을 임의로 정본으로 선택하지 않는다.
- 읽을 수 있었던 과거 QA 증거는 `.cleanup_archives/historical_qa_20260930_verified.zip`에 보관하고 항목 해시를 확인했다. 읽기 권한이 없는 원본 폴더는 삭제하지 않았다.
- 기존 고객 설정·DB·라벨·큐와 세 개의 별도 Git 작업 폴더, SDK/JDK/Gradle, 가상환경, OCR, 글꼴·브랜드·이미지, Android 서명 키를 보존했다.
- 구형 `저장소정리.bat`의 rebase·백업/EXE 삭제·자동 커밋/푸시 동작을 중지했다. 원문은 `.cleanup_archives/legacy_storage_cleanup.bat.txt`에 보관했고 원본 해시와 대조했다.

## 변경 파일

- 루트 `저장소정리.bat`: 구형 자동 정리를 안내 전용으로 변경.
- 루트 `.gitignore`: 로컬 정리 보관본 제외.
- `개발소스/.gitignore`: 디자이너 용량 QA 산출물 제외.
- `website/eslint.config.mjs`, `website-it-public/eslint.config.mjs`: 생성된 빌드 파일과 외부 배포 라이브러리를 lint 대상에서 제외. 애플리케이션 소스 검사는 유지했다.
- 루트 `작업위치_안내.md`: 정본 소스와 새 배포 위치, 별도 Git 작업 폴더 안내 수정.
- 이 보고서 및 `.qa_cleanup_20260930`의 정리·검증 로그.

## 새로 실행한 검증

| 범위 | 결과 |
|---|---|
| Windows Python 전체 pytest | 736개 통과, 기존 Pillow 폐기 예정 경고 7개 |
| Python compileall | 소스 패키지와 스크립트 통과 |
| Windows 공식 clean build | 6개 EXE 모두 성공 |
| EXE 동기화 | dist·정본 루트·고객 실행폴더·상위 최종 폴더·새 고객배포 SHA-256 일치 |
| 정본 및 새 배포 EXE | 디자이너·출력관리 Tk UI 생성 검사 각각 종료 코드 0 |
| 실제 새 디자이너 OCR | 별도 데이터 폴더에서 `LABEL12345678 제품명 채움랩` 인식, 배포본 tools/ocr 엔진 경로 일치 |
| 고객환경점검 | 정상 36개 / 오류 0개, dry-run 포함 |
| 최종 manifest·빈 템플릿 | 유효, elements 빈 배열 유지 |
| 기존 설정·DB·큐·라벨 | 재빌드 전후 해시 유지 |
| website | lint·타입검사·production build·HTML 테스트 15개 통과 |
| website-it-public | lint·타입검사·production build·HTML 테스트 16개 통과 |
| 루트 및 sales-page 정적 HTML | 로컬 파일 참조 110개, 누락 0개 |
| Android 디자이너 | APK 수동 빌드·서명·정렬·manifest 설치 계약 검증 통과 |
| iOS | 정적 계약 검사 통과 |
| 중첩 geobogi 저장소 | 기존 CLI/Excel reader 테스트 15개 통과 |
| 구형 정리 배치파일 | 안내만 표시하고 종료 코드 0, 삭제·Git 동작 없음 |

Python formatter/lint/typecheck 명령과 웹 formatter 명령은 정의되어 있지 않다.
Android 이전 출력 앱은 README상 Android Studio 빌드가 필요한 별도 초안이며 Gradle wrapper가 없다. Python 계약 검사에 포함했지만 해당 앱의 APK를 새로 만들지는 않았다.
iOS 네이티브 빌드·시뮬레이터는 Windows에 Xcode가 없어 실행할 수 없었다.

## 검증된 고객배포

- 새 배포: `고객배포/채움랩_라벨출력_고객용_20260930_01`
- 버전: `2026.09.30.01`, build ID: `20260930_cleanup_verified`
- 디자이너 EXE: 23,672,978바이트. OCR 런타임은 EXE 옆 `tools/ocr`를 사용한다.
- 20260929 및 20260922 배포본을 보존했다. 고객에게는 OCR·글꼴·설정이 포함된 배포 폴더 전체를 전달한다.
- 실제 프린터 출력이나 Android 실기기 설치는 수행하지 않았다. 장비에서 라벨 1장과 스캔·배치·한글을 확인해야 한다.

## 남은 항목

- 보호된 과거 `.tmp`, `.qa_runtime` 및 일부 빈 pytest 디렉터리는 그대로 남아 있다. 권한 변경이나 관리자 강제 삭제는 수행하지 않았다.
- 미완료 `historical_qa_20260930.zip` 1개(49,515,727바이트)의 삭제를 자동 승인 검토가 차단했다. 도구의 사유는 `blocked by policy`이며 구체적인 이유는 제공되지 않았다. 검증된 보관본은 별도 `_verified.zip`이다.
- 중첩 `geobogi-label-project`에는 고객배포 이후 작성된 미커밋 `cli.py`, `excel_reader.py` 변경이 있다. EAN 길이 검증과 Excel 숫자 서식의 선행 0 복원 변경이다. 현재 Windows 정본/고객배포에 합치지 않고 그대로 보존했다. 기존 테스트 15개는 통과했지만 새 동작 전용 회귀 테스트는 없다.
- 최초 Node 실행은 검사 환경에 SystemRoot/WINDIR/사용자 경로 등 Windows 기본 환경변수가 없어 CSPRNG 초기화에 실패했다. 검사 프로세스에만 경로를 보완한 뒤 모든 웹 검증을 완료했다. 시스템 설정·네트워크를 변경한 것은 아니다.
- 주 테스트 경고는 Pillow `getdata` 폐기 예정 경고 7개다.

## 증거와 복구

상세 증거: `개발소스/.qa_cleanup_20260930`의 `inventory_before.json`, `inventory_after.json`, `cleanup_plan.json`, `cleanup_result.json`, `archive_verification.json`, `pytest.log`, `release_build.log`, `release_verification.json`, `customer_preflight_report.txt`, `customer_support_package.zip`, `website_checks.json`, `android_checks.json`, `ios_checks.json`.

과거 고객배포 복구는 프로젝트 루트에서 다음 표준 명령을 사용한다. 원래 `_archive_20260922` 폴더가 복원되며 현재 배포 폴더와 구분된다.

```powershell
tar -xzf "고객배포\_archive_20260922.tar.gz" -C "고객배포"
```

압축파일 SHA-256: `46b296ffc3c17d733ad5d5005a7ed63a252d99265644850564a55a24c51a2cc1`.
복원된 보관본의 동일 파일들은 하드링크일 수 있으므로 고객에게 업데이트용 파일을 제공할 때는 선택한 이전 버전을 별도의 폴더에 일반 복사해 사용한다.
