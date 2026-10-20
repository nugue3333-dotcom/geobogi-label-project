# 채움랩 라벨 출력 패키지

`시작하기.cmd`로 라벨 출력 관리를 열어 상품 엑셀, 도안, 대상과 매수를 확인합니다. 라벨 디자이너에서 도안을 만들고 저장한 뒤 반복 발행에 사용합니다. Excel 매크로 방식은 별도로 `labels.xlsm`의 라벨 출력 버튼을 사용하며 실제 프린터 전송 전 설정과 출력 결과를 확인합니다.

## 고객 PC 설치

고객은 평소 **시작하기.cmd** 한 개로 시작합니다. 제품 EXE는 역할별 실행 파일이며 `tools/ocr` 등의 보조 도구를 직접 고를 필요가 없습니다. 이전 도안 접수, 새 PC 업데이트와 복구 절차는 아래 문서에서 확인합니다.

- [고객 도안 이전 가이드](docs/BARTENDER_MIGRATION.md) / [원본·이전 결과 대조표](docs/TEMPLATE_MIGRATION_CHECKLIST.md)
- [업데이트·PC 교체·복구](docs/UPDATE_AND_RECOVERY.md)
- [실물 장비 승인 기록 양식](docs/DEVICE_ACCEPTANCE_RECORD.md) / [공개 호환성 기준](docs/PRODUCT_PACKAGES.md)
- [유료 조건 승인대기표](docs/PAID_SUPPORT_TERMS_DRAFT.md): 가격·설치·이전·지원 조건은 승인 전에는 고객 약정으로 사용하지 않습니다.

라벨디자이너의 도안 글자 인식 엔진은 배포 폴더의 `tools/ocr`에서 실행합니다.
EXE 안에는 같은 엔진을 중복 저장하지 않습니다. `라벨디자이너.exe`만 따로
옮기지 말고 `tools/ocr`와 글꼴·설정이 포함된 배포 폴더 전체를 복사하세요.

1. `고객용_실행폴더` 전체를 고객 PC 원하는 위치에 복사합니다.
2. `처음실행_점검.cmd`를 실행해 필수 파일, 설정, 엑셀, `.cllabel`·`.clproject`와 구버전 저장파일 연결, 출력 폴더, dry-run 결과를 확인합니다. `시작하기.cmd`는 라벨출력관리 화면을 바로 엽니다. 번호 메뉴가 필요하면 `시작하기.cmd menu`를 실행하세요.
   오류가 있으면 `out\customer_preflight_report.txt`를 확인하거나 `out\customer_support_package.zip`을 지원 담당자에게 전달합니다.
3. 저장파일 더블클릭/아이콘만 다시 등록해야 할 때는 `시작하기.cmd file-association` 또는 `register_label_filetype.cmd`를 실행합니다. 기존 `.gblabel`·`.gbproject` 파일도 계속 열 수 있습니다.
4. Excel 매크로 방식도 사용할 경우 처음 한 번 `00_install_trusted_location.cmd`를 실행합니다.
5. `프린터설정.exe`를 실행해 브랜드, 연결 방식, 용지 크기, 인쇄 방식을 입력한 뒤 `설정 점검`을 눌러 저장 전 오류를 확인하고 저장합니다.
6. 업데이트 배포본을 다시 복사해도 기존 `config.ini`가 있으면 고객 프린터 설정은 자동으로 덮어쓰지 않습니다. 기본값으로 되돌릴 때만 백업 후 `config.example.ini`를 참고하세요.
7. `라벨출력관리.exe`에서 DB를 연결하고 출력할 항목을 추가합니다. 체크한 항목이 있으면 해당 항목, 없으면 전체 유효 항목이 대상입니다. 인쇄 버튼에서 매수를 확인하고 인쇄를 시작합니다. 매수 변경은 임시 큐에만 적용되며 연결 DB와 기본 출력 목록을 덮어쓰지 않습니다. Excel 매크로 방식은 `labels.xlsm`의 `라벨 출력` 버튼을 사용합니다.

## 통합 디자인과 저장파일

- 세 프로그램은 채움랩 원본 로고, 딥블루 `#143E70`, 라임 `#A3D900`, 동일한 메뉴·버튼·상태 표시를 사용합니다.
- 화면 글꼴은 맑은 고딕입니다. 라벨에 지정된 출력 글꼴은 그대로 유지됩니다.
- 라벨디자이너는 상단의 `좌우 가운데 정렬`·`상하 가운데 정렬`, 왼쪽 도구 카드, 오른쪽 DB 카드로 구성됩니다. `인식 값 전체 확인`에서 도안 인식 결과를 한 번에 검토합니다.
- 새 라벨은 `.cllabel`, 도안·이미지와 글꼴 목록을 묶는 프로젝트는 `.clproject`로 저장합니다. 글꼴 파일과 상품 엑셀 원본은 별도로 준비합니다. 기존 파일의 일반 저장은 기존 확장자를 유지하며, 새 확장자는 다른 이름으로 저장할 때 선택합니다.
- 세 프로그램의 `도움말 > 고객용 매뉴얼`에서 해당 PDF를 엽니다. 통합 Word 문서는 `채움랩_라벨출력패키지_고객용_매뉴얼.docx`입니다.

## 사용편의 개선 (2026.10.07.01)

- 개체 선택 후 Ctrl+C / Ctrl+V / Ctrl+D로 복사·붙여넣기·복제합니다. 글자 입력칸의 편집은 해당 글자를 우선합니다. 다중 선택, 그림, DB 연결과 실행취소를 지원합니다.
- 개체 도구 8종은 아이콘과 이름을 함께 표시합니다.
- 라벨 규격은 프린터 설정에서 한 번 저장합니다. 디자이너의 읽기 전용 규격 표시와 출력 관리가 같은 설정을 사용하며, 용지 설정 바로가기로 변경합니다. 다른 규격의 도안은 열 때 규격 사용 방법을 선택하고 개체가 영역을 벗어나는 변경은 취소합니다.
- 인쇄 매수는 상한 없는 양의 정수이며 대상 수 × 매수의 총 매수를 확인합니다. 전송 중 중단은 미전송 작업을 멈춥니다. 프린터가 이미 수신한 작업의 중단은 보장하지 않습니다.

## 값 생성 규칙 (2026.10.20.02)

- 디자이너의 `도구 > 값 생성 규칙`에서 생성 필드를 만든 뒤 텍스트·바코드 편집창의 데이터 원본에서 해당 필드를 연결합니다. 규칙을 저장한 도안을 출력 관리에서 선택하고 전체 데이터 검증을 거칩니다.
- 일련번호는 증가·감소, 숫자·영문 대문자·영문 소문자·숫자+영문 대문자, 자리수 유지·자동 자리수를 지원합니다. 번호당 복사 수와 작업마다 시작·계속 발급을 설정할 수 있습니다. 예: 영문 대문자 `Z` 다음은 `AA`, 숫자+영문은 `09` 다음 `0A`입니다.
- DB 열을 변경 대상으로 고르면 1부터 세는 시작 위치와 글자 수만큼 순번으로 바꾸고 나머지 원문은 보존합니다. 예: `ABC00042`의 4번째부터 5글자를 `00001`로 바꾸면 `ABC00001`이 됩니다. 바꿀 글자 수와 순번 자리수는 같아야 합니다.
- 미리보기는 번호를 소비하지 않습니다. 증가·감소가 허용 범위를 벗어나거나 원본 열·부분 범위가 맞지 않으면 출력 전 검증에서 차단합니다. 계속 발급은 명시적으로 인쇄를 확정한 작업만 기록하며, 취소한 번호는 자동 재사용하지 않습니다. 재인쇄는 확정된 작업의 저장값을 다시 사용합니다.

## 프린터 설정 프로그램

고객 배포 폴더의 `프린터설정.exe`에서 아래 항목을 클릭으로 변경합니다.

- 브랜드: BIXOLON / 빅솔론, TSC, Zebra / 제브라, SEWOO / 세우테크 (ZPL)
- 연결 방식: LAN / 네트워크, USB / Windows 프린터
- 용지 크기: 가로, 세로, 간격, DPI
- 인쇄 방식: 감열 / 리본 없음, 열전사 / 리본 사용
- 저장 전 점검: IP/포트, Windows 프린터 이름, 용지 유형, 간격, DPI, 브랜드별 인쇄후작업 지원 여부

설정 프로그램은 같은 폴더의 `config.ini`를 자동으로 갱신합니다. 저장 전 점검에서 오류가 나오면 저장하지 않으므로 고객 배포 시에는 `config.ini`를 직접 수정하지 않아도 됩니다. 기존 고객 데이터 폴더에 `config.ini`가 있으면 업데이트 배포본의 기본 설정으로 자동 교체하지 않습니다.

## config.ini 기본 구조

```ini
[printer]
brand = bixolon
mode = network
print_method = direct_thermal
language = auto
command_encoding = auto
ip = 192.168.0.130
port = 9100
windows_printer_name = auto

[label]
width_mm = 50
height_mm = 30
dpi = 203
gap_mm = 3
media_type = gap

[data]
excel_file = print_queue.xlsx
output_dir = out
```

`mode = network`는 프린터 IP와 9100 포트로 RAW 명령을 보냅니다. Windows 프린터 드라이버 큐를 통해 보낼 때는 `mode = windows_raw`로 바꾸고 `windows_printer_name`을 실제 프린터 이름으로 입력합니다.

`print_method = direct_thermal`은 감열 방식입니다. 열전사 방식은 `thermal_transfer`로 저장됩니다.

`command_encoding = auto`는 한글 출력용 바이트 인코딩을 브랜드별 기본값으로 선택합니다. BIXOLON은 `cp949`, TSC/Zebra/SEWOO는 `utf-8`입니다. SEWOO는 ZPL 호환 세우테크 모델 기준입니다.

`media_type`은 용지 센서 방식을 지정합니다. 갭 라벨은 `gap`, 블랙마크 라벨은 `black_mark`, 연속 용지는 `continuous`를 사용합니다.

## 검증 명령

Windows의 여러 Tk 창을 한 테스트 프로세스에서 반복 생성하면 Tcl 초기화 오류가 간헐적으로 발생할 수 있습니다. 출시 검증은 전체 단위·통합 테스트와 실제 GUI 시나리오를 각각 새 Python 프로세스에서 실행합니다. Windows 심볼릭 링크 생성 권한이 없는 경우 안내 갱신 도구의 링크 관련 2개 테스트는 사유를 표시하고 건너뜁니다.

```powershell
.\.venv\Scripts\python.exe scripts\verify_release_tests.py
```

```powershell
.\.venv\Scripts\python.exe -m pytest --basetemp .\pytest_tmp
.\고객용_실행폴더\고객환경점검.exe --base-dir .\고객용_실행폴더
type .\고객용_실행폴더\out\customer_preflight_report.txt
dir .\고객용_실행폴더\out\customer_support_package.zip
.\고객용_실행폴더\라벨출력엔진.exe --config .\고객용_실행폴더\config.ini --dry-run
.\프린터설정.exe --show-config-path
```

6개 고객용 EXE clean 빌드, `dist` 정리, 소스 루트/`고객용_실행폴더`/상위 최종 폴더 동기화, SHA-256 일치 확인, 전체 고객 payload manifest 생성은 아래 한 명령으로 수행합니다. `-TestResult`에는 직전에 실행한 테스트의 실제 결과를 입력합니다.

```powershell
pwsh -NoProfile -ExecutionPolicy Bypass -File .\scripts\build_release_exes.ps1 -Version (Get-Date -Format "yyyy.MM.dd.HHmm") -TestResult "pytest: 실제 통과 결과"
```

빌드 대상은 `고객환경점검.exe`, `라벨디자이너.exe`, `라벨작업실행기.exe`, `라벨출력관리.exe`, `라벨출력엔진.exe`, `프린터설정.exe`입니다. 생성된 `release_manifest.json`은 런타임 생성물을 제외한 고객 폴더의 모든 배포 파일과 package/version/build 정보, 6개 spec 해시, Python/PyInstaller 버전, 입력한 테스트 결과를 기록합니다.

## 모바일 앱

Android 모바일 앱 소스는 `mobile-android` 폴더에 있습니다. 무선랜/LAN 출력과 Bluetooth Classic SPP 출력을 지원합니다. APK 빌드는 Android Studio에서 `mobile-android` 폴더를 열어 진행합니다.
## BarTender 도안 전환

기존 `.btw` 도안은 직접 열 수 없습니다. 이미지 기반 재작성과 현장 확인 절차는 [BarTender 도안 전환 안내](docs/BARTENDER_MIGRATION.md)를 참고하세요.
