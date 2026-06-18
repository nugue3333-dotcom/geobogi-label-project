# 거복이의꿈 라벨 출력 패키지

엑셀 `labels.xlsm`에 품목 정보를 입력하고 `라벨 출력` 버튼을 누르면 `print_queue.xlsx`를 다시 만든 뒤 설정된 프린터로 바로 전송합니다.

## 고객 PC 설치

1. `고객용_실행폴더` 전체를 고객 PC 원하는 위치에 복사합니다.
2. 처음 한 번 `00_install_trusted_location.cmd`를 실행합니다.
3. `프린터설정.exe`를 실행해 브랜드, 연결 방식, 용지 크기, 인쇄 방식을 저장합니다.
4. `labels.xlsm`을 열고 데이터를 입력한 뒤 `라벨 출력` 버튼을 누릅니다.

## 프린터 설정 프로그램

고객 배포 폴더의 `프린터설정.exe`에서 아래 항목을 클릭으로 변경합니다.

- 브랜드: BIXOLON / 빅솔론, TSC, Zebra / 제브라
- 연결 방식: LAN / 네트워크, USB / Windows 프린터
- 용지 크기: 가로, 세로, 간격, DPI
- 인쇄 방식: 감열 / 리본 없음, 열전사 / 리본 사용

설정 프로그램은 같은 폴더의 `config.ini`를 자동으로 갱신합니다. 고객 배포 시에는 `config.ini`를 직접 수정하지 않아도 됩니다.

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

[data]
excel_file = print_queue.xlsx
output_dir = out
```

`mode = network`는 프린터 IP와 9100 포트로 RAW 명령을 보냅니다. Windows 프린터 드라이버 큐를 통해 보낼 때는 `mode = windows_raw`로 바꾸고 `windows_printer_name`을 실제 프린터 이름으로 입력합니다.

`print_method = direct_thermal`은 감열 방식입니다. 열전사 방식은 `thermal_transfer`로 저장됩니다.

`command_encoding = auto`는 한글 출력용 바이트 인코딩을 브랜드별 기본값으로 선택합니다. BIXOLON/TSC는 `cp949`, Zebra는 `utf-8`입니다.

## 검증 명령

```powershell
.\.venv\Scripts\python.exe -m pytest --basetemp .\pytest_tmp
.\고객용_실행폴더\print_labels.exe --config .\고객용_실행폴더\config.ini --dry-run
.\printer_settings.exe --show-config-path
```

빌드:

```powershell
.\.venv\Scripts\python.exe -m PyInstaller --clean --noconfirm .\print_labels.spec
.\.venv\Scripts\python.exe -m PyInstaller --clean --noconfirm .\printer_settings.spec
```

## 모바일 앱

Android 모바일 앱 소스는 `mobile-android` 폴더에 있습니다. 무선랜/LAN 출력과 Bluetooth Classic SPP 출력을 지원합니다. APK 빌드는 Android Studio에서 `mobile-android` 폴더를 열어 진행합니다.
