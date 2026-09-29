# 채움LAB 모바일 라벨 Android

설치 패키지 ID는 `kr.chaeumlab.mobilelabel`입니다. 이후 업데이트가 같은
제작자 서명으로 인식되도록 `signing/chaeumlab-sideload.keystore`를 빌드 간
유지합니다. 이 키 파일을 삭제하면 기존 설치본 위에 업데이트할 수 없습니다.

기존 `mobile-android` 출력 앱을 덮어쓰지 않은 새 Android 전용 라벨 편집 앱입니다.

## 현재 기능

- 첫 실행 빈 템플릿
- 객체: 텍스트, 1D 바코드, QR, 박스, 선
- 객체 이동, 크기, 복제, 삭제, 회전 `0/90/180/270`
- PC 호환 JSON 템플릿 저장/불러오기
- CSV 가져오기, 전체 열 검색, 행 선택, 출력 매수 `1~100`
- 무선 LAN 연결 확인과 명령 전송
  - 프린터 IP/포트 입력
  - 브랜드: TSC, BIXOLON, Zebra, SEWOO
  - DPI: 203, 300, 600
  - 용지: 갭, 블랙마크, 연속
  - 인쇄 후 작업: 뜯어내기, 커터, 필러

## 연결 방식

모바일 출력은 무선 LAN 전용입니다. USB, Bluetooth, Windows 드라이버 큐 출력은 이 앱에 넣지 않았습니다.

## 빌드 방법

### 명령줄에서 빌드

이 PC는 Gradle 데몬이 Windows Winsock 오류로 실행되지 않아, `build_apk_manual.ps1`가 Android SDK 도구를 직접 호출해서 APK를 생성합니다.

```powershell
cd ".\개발소스\mobile-android-designer"
.\build_apk_manual.ps1
```

생성 파일:

- `dist\mobile-label-designer-debug.apk`
- `dist\채움LAB_모바일라벨-debug.apk`

### Android Studio에서 빌드

1. Android Studio를 설치합니다.
2. Android Studio에서 이 폴더를 엽니다.
   - `.\개발소스\mobile-android-designer`
3. Android SDK Platform 35와 JDK 17 환경에서 Gradle Sync를 실행합니다.
4. `Build > Build Bundle(s) / APK(s) > Build APK(s)`를 실행합니다.

## 검증 주의

- 앱의 `명령 전송 완료`는 휴대폰에서 프린터로 TCP 명령 전송이 끝났다는 뜻입니다.
- 실제 출력 성공은 프린터가 라벨을 정상 배출하는지로 별도 확인해야 합니다.
- 현재 바코드 미리보기는 화면 배치를 위한 간이 표현입니다. 실제 출력 명령은 프린터의 1D Code128 명령으로 생성합니다.
- BIXOLON은 CP949, TSC/Zebra/SEWOO는 UTF-8로 전송합니다.
- BIXOLON 필러는 차단됩니다. SEWOO는 승인 모델 근거가 없어 뜯어내기만 허용됩니다.
- 실제 프린터 전송 검증은 하지 않았으며, 실패 후 앱 상태를 해제해 즉시 재시도할 수 있습니다.
