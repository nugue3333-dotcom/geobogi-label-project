# 라벨 출력 모바일 Android 앱

Android 휴대폰에서 라벨 프린터로 직접 출력하는 모바일 앱입니다.

## 지원 연결 방식

- 무선랜 / LAN: 프린터 IP와 포트로 RAW 명령을 전송합니다. 기본 포트는 `9100`입니다.
- 블루투스: Android에 이미 페어링된 Bluetooth Classic SPP 프린터로 RAW 명령을 전송합니다.

## 지원 브랜드

- BIXOLON / 빅솔론: SLCS 명령, 한글 인코딩 `MS949`
- TSC: TSPL 명령, 한글 인코딩 `MS949`
- Zebra / 제브라: ZPL 명령, 한글 인코딩 `UTF-8`

## 앱에서 설정하는 항목

- 연결 방식: 무선랜 / LAN, 블루투스
- 프린터 브랜드: BIXOLON, TSC, Zebra
- 인쇄 방식: 감열 / 리본 없음, 열전사 / 리본 사용
- 용지: 가로(mm), 세로(mm), 라벨 간격(mm), DPI
- 라벨 데이터: 품목 코드, 품목명, 바코드, LOT 번호, 수량, 출력 매수

## 빌드 방법

이 PC에는 Android SDK, Gradle, JDK가 설치되어 있지 않아 APK 빌드는 로컬에서 검증하지 않았습니다.

1. Android Studio를 설치합니다.
2. Android Studio에서 이 폴더를 엽니다.
   - `C:\Users\기술부\Documents\New project\거복이의꿈\mobile-android`
3. Android SDK Platform 35와 JDK 17 환경으로 Gradle Sync를 실행합니다.
4. `Build > Build Bundle(s) / APK(s) > Build APK(s)`를 실행합니다.
5. 생성된 APK를 Android 휴대폰에 설치합니다.

## 사용 전 준비

### 무선랜 / LAN

1. 휴대폰과 라벨 프린터가 같은 네트워크에 있어야 합니다.
2. 프린터 IP를 확인합니다.
3. 앱에서 연결 방식을 `무선랜 / LAN`으로 선택하고 IP, 포트를 입력합니다.

### 블루투스

1. Android 설정에서 라벨 프린터를 먼저 페어링합니다.
2. 앱에서 연결 방식을 `블루투스`로 선택합니다.
3. `블루투스 목록 새로고침`을 누르고 프린터를 선택합니다.

## 제한 사항

- 현재 프로젝트는 Android용입니다.
- iPhone은 일반 Bluetooth Classic/SPP 프린터 직접 연결이 제한됩니다. iPhone 지원이 필요하면 해당 프린터가 BLE 또는 제조사 iOS SDK를 지원하는지 먼저 확인해야 합니다.
- Bluetooth BLE 전용 프린터는 현재 앱의 Bluetooth SPP 방식으로 출력할 수 없습니다.
