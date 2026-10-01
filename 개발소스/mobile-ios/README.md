# 채움LAB 모바일 iOS

SwiftUI 기반 iPhone/iPad 라벨 편집 및 무선 LAN 출력 앱입니다. 기본 템플릿은 객체가 없는 빈 상태이며, 하단 탭에서 `템플릿`, `데이터`, `출력`, `설정` 작업을 분리합니다.

## 구현 범위

- 텍스트, 1D 바코드, QR 코드, 박스, 선 객체 추가
- 객체 위치/크기 편집과 0/90/180/270도 회전
- PC 템플릿 JSON 호환 import/export
  - `label.width_mm`, `label.height_mm`
  - `type`, `text`, `field`, `x`, `y`, `width`, `height`, `rotation`
- CSV 불러오기, 모든 열 통합 검색, 행 선택/전체 선택/선택 해제
- 선택 행별 출력 매수 1~100
- TSC, BIXOLON, Zebra, SEWOO TCP RAW LAN 출력
- 203/300/600 DPI, 감열/열전사, 갭/블랙마크/연속 용지
- 연결 확인, 전송 실패 표시, 마지막 작업 즉시 재시도

## 프린터 계약

- TSC: UTF-8, 뜯어내기/커터/필러 허용
- BIXOLON: CP949, 뜯어내기/커터 허용, 필러 차단
- Zebra: UTF-8, 뜯어내기/커터/필러 허용
- SEWOO: UTF-8, 승인 모델 근거가 없어 뜯어내기만 허용
- 성공 상태는 `명령 전송 완료`로 표시하며 실제 용지의 `인쇄 완료`와 구분

## 연결 조건

- iPhone/iPad와 프린터가 같은 Wi-Fi 네트워크에 있어야 합니다.
- 기본 TCP RAW 포트는 `9100`입니다.
- Bluetooth Classic/SPP, USB, Windows 프린터 큐는 지원하지 않습니다.

## 빌드

Mac에서 `GeobogiLabelMobile.xcodeproj`를 Xcode로 열고 iOS 17 이상 대상에서 빌드합니다.

이 Windows 작업 환경에는 Xcode와 iOS Simulator가 없어 실제 컴파일, 시뮬레이터 실행, 실물 프린터 출력은 수행할 수 없습니다. 실제 배포 전 Mac에서 빌드하고 각 제조사 프린터로 최소 1장씩 위치, 크기, 한글, 용지 감지, 인쇄후작업을 확인해야 합니다.
