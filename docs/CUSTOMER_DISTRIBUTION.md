# 소비자 판매 패키지 배포 방법

## 목표

고객에게는 실행 파일, 기본 설정 예시, 템플릿, 사용 안내만 전달하고 개발소스, 자동화 설정, 로그, 로컬 고객 데이터는 전달하지 않습니다.

## 생성 명령

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\build_customer_package.ps1
```

샘플 엑셀까지 포함하려면 아래처럼 실행합니다.

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\build_customer_package.ps1 -IncludeSampleWorkbooks
```

## 기본 포함 파일

- `라벨출력관리.exe`
- `라벨디자이너.exe`
- `프린터설정.exe`
- `print_labels.exe`
- `config.example.ini`
- `config.ini` (example 기준으로 생성)
- `templates/`
- `사용안내.txt`
- `라벨출력패키지_고객용_매뉴얼.docx`
- `index.html`
- `assets/higgsfield/hero.png`
- `고객_시작안내.txt`

## 기본 제외 항목

- `개발소스/`
- `.agent/`
- `.agents/`
- `.stitch/`
- `.git/`
- `_backup/`
- `out/`
- 로그 파일
- 현재 작업용 `config.ini`
- 승인되지 않은 가격, 보증, 환불, 배송 정책 문서

## 고객 전달 전 체크

1. 고객명, 연락처, 주소, 주문 정보가 포함된 파일이 없는지 확인합니다.
2. `config.ini`가 고객 환경에 맞게 조정되어야 함을 안내합니다.
3. 실제 프린터 출력 전 dry-run 또는 미리보기로 확인합니다.
4. 설치지원, 보증, 환불, 배송 조건은 별도 문서로 확정한 뒤 전달합니다.

