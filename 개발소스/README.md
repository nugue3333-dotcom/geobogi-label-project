# 채움랩 라벨 출력 패키지

엑셀 `labels.xlsm`에 품목 정보를 입력하고 `라벨 출력` 버튼을 누르면 `print_queue.xlsx`를 다시 만든 뒤 설정된 프린터로 바로 전송합니다.

## 고객 PC 설치

1. `고객용_실행폴더` 전체를 고객 PC 원하는 위치에 복사합니다.
2. `시작하기.cmd`를 실행하고 `1. 처음 실행 점검`을 선택해 필수 파일, 설정, 엑셀, `.gblabel` 저장파일 연결, 출력 폴더, dry-run 결과를 확인합니다.
   오류가 있으면 `out\customer_preflight_report.txt`를 확인하거나 `out\customer_support_package.zip`을 지원 담당자에게 전달합니다.
3. `.gblabel` 저장파일 더블클릭/아이콘만 다시 등록해야 할 때는 `시작하기.cmd file-association` 또는 `register_label_filetype.cmd`를 실행합니다.
4. Excel 매크로 방식도 사용할 경우 처음 한 번 `00_install_trusted_location.cmd`를 실행합니다.
5. `프린터설정.exe`를 실행해 브랜드, 연결 방식, 용지 크기, 인쇄 방식을 입력한 뒤 `설정 점검`을 눌러 저장 전 오류를 확인하고 저장합니다.
6. 업데이트 배포본을 다시 복사해도 기존 `config.ini`가 있으면 고객 프린터 설정은 자동으로 덮어쓰지 않습니다. 기본값으로 되돌릴 때만 백업 후 `config.example.ini`를 참고하세요.
6. `labels.xlsm`을 열고 데이터를 입력한 뒤 `라벨 출력` 버튼을 누릅니다.

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
