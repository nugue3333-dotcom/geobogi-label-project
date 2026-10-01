# 2026.09.29.01 — 라벨디자이너 실행파일 용량 축소

## 변경

- `label_designer.spec`에서 OCR 엔진의 EXE 내부 중복 포함을 제거했다.
- 기존 배포 폴더의 `tools/ocr` 94개 파일은 그대로 유지했다. 제품의 OCR 탐색 코드는 변경하지 않았다.
- EXE 크기: 136,420,420 → 23,671,777바이트, 82.65% 감소.
- 고객배포 폴더 전체 크기: 417,745,397 → 306,602,021바이트.
- 배포: `고객배포/채움랩_라벨출력_고객용_20260929_01`.
- EXE만 옮기지 않고 배포 폴더 전체를 복사하도록 README에 안내했다.

## 검증

- pytest 736개 통과. 기존 Pillow getdata 폐기 예정 경고 7개.
- Python compileall 통과. 별도 formatter/lint/typecheck 명령은 정의되어 있지 않다.
- 공식 스크립트로 6개 EXE clean build 및 manifest 검증 통과.
- dist, 개발소스 루트, 고객용 실행폴더, 상위 최종 폴더, 새 고객배포의 6개 EXE SHA-256 일치.
- 실제 새 EXE의 디자이너/출력관리 smoke 및 Tk UI 생성 검사 모두 종료 코드 0.
- 별도 고객 데이터 경로에서 실제 디자이너 EXE로 이미지 분석: `LABEL12345678 제품명 채움랩` 인식.
- OCR 엔진 경로가 새 배포본의 `tools/ocr/tesseract.exe`임을 확인했다.
- 고객환경점검: 정상 36개 / 오류 0개. dry-run 출력 전 검증 포함.
- 기본 템플릿 elements는 빈 배열 유지. 최종 배포 manifest 유효.
- 검증 산출물: `qa_designer_size_20260929/verification.json`, `customer_preflight_report.txt`, `customer_support_package.zip`, `build.log`.

## 알려진 제한과 복구

- 실제 프린터 출력은 수행하지 않았다. 고객 장비에서 기존 절차대로 라벨 1장을 확인한다.
- EXE만 단독 복사하면 OCR이 작동하지 않을 수 있으므로 `tools/ocr`를 함께 보관한다.
- 보호된 과거 PyInstaller 임시 폴더 10개의 자동 정리는 권한 때문에 보류되었다. 새 배포/실행 검증은 통과했다.
- 빌드 첫 시도는 USERPROFILE 미설정 때문에 중단됐다. 빌드 프로세스에 기존 사용자 경로를 지정한 뒤 성공했다.
- 이전 배포 `채움랩_라벨출력_고객용_20260922_01`은 보존했다. 복구 시 고객 설정과 데이터는 먼저 백업하고 이전 프로그램 배포본을 사용한다.
