# 채움랩 수정·검증·배포 완료 보고서

버전: **2026.10.12.01** · 빌드: paid_20261012_01 · 기준: 10월 8일 승인 수정안 + 10월 12일 제공 GS1 표시 참고 코드

## 1. 완료 결과

- 라벨 디자이너와 저장 도안 반복 출력에서 GS1 DataMatrix는 표시문자(HRI)를 켜면 바코드 오른쪽에 AI별 데이터를 여러 줄로 표시합니다. GS1-128은 하단에 AI 괄호를 포함한 전체 값을 표시합니다.
- 제공 코드의 표시 방향과 AI 묶음 방식을 반영했습니다. 48자 잘림·문자 임의 제거·비정수 모듈 축소는 적용하지 않았습니다. 공간이 부족하면 출력 전 오류로 안내합니다. 기존 표시 끄기 선택은 유지됩니다.
- GS1 편집 중 선택 행 수정값이 검증·적용에 반영되며 취소는 원본을 유지합니다. 필수 AI 조합 안내·후보 선택·한국어 검색·자주 쓰는 AI 목록을 보완했습니다. 실제 상품 식별번호를 임의 생성하지 않습니다.
- 저장한 현재 도안을 반복 출력 관리로 전달하고 같은 렌더러로 미리보기·전체 데이터 검증·출력 명령을 만듭니다. 자동 기본 배치는 명시적으로 구분합니다.
- 엑셀 파일·시트·열·원본/복사본·갱신 상태를 기록하고 변경·분실 시 재연결을 안내합니다. 재연결한 데이터 맥락도 도안에 보존합니다.
- 일련번호, 날짜/기한, 문자 결합, 부분 추출 규칙을 추가했습니다. 미리보기·인쇄파일 생성은 번호를 소비하지 않습니다. 확정된 값과 날짜는 작업 기록으로 보존합니다.
- 마지막 생성 작업 재인쇄는 원본 엑셀 없이도 저장된 값을 재사용합니다. 도안 내용이 바뀌면 원래 도안을 복원하도록 차단합니다. 번호 발급 초기화는 중복 위험을 확인한 뒤 실행합니다.
- 발급 기록은 고객 백업에 포함하며 번호가 뒤로 돌아가거나 작업 기록이 빠지는 복원을 차단합니다.
- 상단 문서·편집·정렬·출력 묶음, 선택 개체 편집/복제/잠금, 인쇄 범위 표시를 정리했습니다. 기존 브랜드와 우측 DB 전용 구조를 유지했습니다.
- 시작 직후의 새 편집을 이전 복구 작업으로 오인하는 오류를 수정했습니다. 시작 전에 존재한 기록만 복구 대상으로 삼고 기존 복구 기록은 선택 전까지 보존합니다.
- 프로그램 매뉴얼 PDF 3종, Word 매뉴얼, 빠른 안내와 전환/복구 문서를 갱신했습니다. 실제 화면 캡처와 PDF 주요 페이지를 검토했습니다.

## 2. 주요 변경 파일

`barcode_label_automation/label_designer_app.py`, `label_manager_app.py`, `gs1.py`, `gs1_editor.py`, `barcode_options_dialog.py`, `settings_app.py`, `print_progress.py`, `customer_backup.py`, `customer_deployment.py`, `release_manifest.py`, `ui_style.py`

신규 작업 모듈: `job_profile.py`, `template_output.py`, `saved_output.py`, `profile_dialogs.py`, `value_rules.py`, `value_jobs.py`, `value_rules_dialog.py`

검증: `tests/test_gs1_hri_layout.py`, `tests/test_paid_output_workflow.py`, 복구·GUI·값 생성·백업 테스트. 문서/빌드: `scripts/build_customer_manuals.py`, `create_customer_manual.py`, `capture_customer_manual_screens.py`, `verify_release_tests.py`, `build_release_exes.ps1` 및 docs 전환·장비 승인·복구·지원 조건 문서.

## 3. 실행 검증과 결과

| 항목 | 결과 |
|---|---|
| 전체 단위·통합·GUI 테스트 | **6,489개 통과 / 2개 제외 / 실패 0** |
| GUI 프로세스 | 38개 별도 프로세스로 실행. 확대 배율·창 경계·편집·취소·GS1 조합·옵션·복사/붙여넣기·10,000장 입력 포함 |
| 해상도·배율 추가 점검 | 1366×768 / 1920×1080의 100·150·200% 6조합 통과. 실제 Tk 창의 상단 핵심 메뉴 경계를 검사. 작업영역과 DPI는 테스트에서 지정했으며 물리 모니터 해상도는 변경하지 않음 |
| 근접 문서·도안·GS1 회귀 | 55개 재통과. 전체 테스트에도 포함되므로 합산하지 않음 |
| Python 구문 컴파일 | compileall 통과 |
| formatter/lint/typecheck | 저장소에 실행 명령/설정이 정의되지 않아 별도 실행 없음 |
| 배포 실행파일 | clean 빌드 6개. 개발소스·실행폴더·상위 최종·신규 배포의 SHA-256 동일 |
| EXE 검증 | 73개 실행 점검 통과. 실제 UI smoke, 인쇄파일 생성, 매수 경계, 이동 프로젝트, 한글 명령, 고객 preflight 포함 |
| 배포 EXE 독립 판독 | 12개 통과. SLCS/TSPL/ZPL의 QR·GS1-128 및 저장 도안의 GS1 DataMatrix/GS1-128 HRI 명령을 이미지로 복원해 원본 바이트와 대조 |
| 고객 데이터·설정 | 24개 보호 파일 SHA-256 유지. 기본 템플릿 elements=[] 유지 |
| 매뉴얼 | PDF 13/9/8페이지, Word 및 안내문 검증·복사본 일치. PDF 주요 페이지 시각 검토 |

제외된 테스트와 사유:

- tests.test_customer_guide_package.test_rejects_linked_guide: Windows symbolic-link privilege unavailable; run these two tests on CI or with Developer Mode
- tests.test_customer_guide_package.test_link_inserted_during_copy_prevents_publication: Windows symbolic-link privilege unavailable; run these two tests on CI or with Developer Mode

세부 증거는 개발소스 `outputs/paid-product-20261012/`의 verified-final/result.json, built-release-result.json, frozen-barcode/result.json, preserved-data-result.json 및 매뉴얼 검증 로그에 있습니다. 중간 실패·시간 초과 로그도 보존했습니다. 시작 복구 대기 오류는 수정 후 전체 검증을 다시 통과했습니다.

## 4. 배포 파일

고객 배포 폴더: **C:\Users\기술부\Desktop\거복이의꿈최종\고객배포\채움랩_라벨출력_고객용_20261012_01**

| 프로그램 | 용량 |
|---|---|
| 고객환경점검.exe | 18.87 MB |
| 라벨디자이너.exe | 22.78 MB |
| 라벨작업실행기.exe | 18.85 MB |
| 라벨출력관리.exe | 22.89 MB |
| 라벨출력엔진.exe | 21.62 MB |
| 프린터설정.exe | 19.73 MB |

전달용 ZIP: **C:\Users\기술부\Desktop\거복이의꿈최종\고객배포\채움랩_라벨출력_고객용_20261012_01.zip** (197.39 MB). 202개 파일의 압축 해제 내용과 배포 폴더 원본 SHA-256을 모두 대조했습니다.

고객 시작점은 `시작하기.cmd`입니다. 루트의 불필요한 OCR 보조 EXE는 개발소스 `.release-preserved-tools/paid_20261012_01/`에 보존하며 실제 OCR 경로 tools/ocr은 유지합니다. 고객 프린터 설정과 데이터는 덮어쓰지 않았습니다.

## 5. 실물 확인과 남은 범위

- 이번 검증은 인쇄 명령 생성·복원·소프트웨어 판독 및 UI 검증입니다. 실제 프린터 전송·라벨 배출·실물 스캐너 판독은 실행하지 않았습니다. 고객 용지, DPI, 리본/감열, 센서·후처리로 첫 장을 출력해 확인해야 합니다.
- BarTender 2022 Professional의 모든 종류·옵션과 완전 동일하다는 검증은 아닙니다. 공식 69개 형식 주제 중 대응 57개이며 미지원 형식/옵션은 기존 지원 대조표에 명시합니다.
- 실제 고객 BarTender 도안 3개 이상의 재작성·가변 값·GS1·레이아웃·실물 판독 비교는 전환 체크리스트로 확인해야 합니다. .btw 직접 편집/완전 변환을 보장하지 않습니다.
- 장비별 승인 기록과 지원 기간·라이선스·비용 조건은 승인용 문서로 준비했으며 확정된 정책이나 승인된 장비라고 표시하지 않습니다.
- 서로 다른 번호를 매우 많이 생성하면 작업 기록과 메모리 사용이 증가합니다. 실제 대량 작업의 처리 시간은 고객 데이터·개체 수로 확인해야 합니다.
- GitHub 업로드, 코드 서명, 고객 전달/설치, 운영 배포는 이번 결과에 포함하지 않습니다.

GS1 표시 원칙 확인: [GS1 DataMatrix 공식 가이드](https://ref.gs1.org/guidelines/datamatrix/). 사람이 읽는 AI 괄호와 인코딩 데이터를 구분합니다.
