# 소비자 판매 패키지 배포 방법

## 목표

고객에게는 실행 파일, 기본 설정 예시, 템플릿, 사용 안내만 전달하고 개발소스, 자동화 설정, 로그, 로컬 고객 데이터는 전달하지 않습니다.

## 현재 실행 파일 릴리스 경로와 그림 안내

현재 고객용 실행 파일은 `개발소스/scripts/build_release_exes.ps1`의 릴리스 게이트로 생성합니다. 아래의 `build_customer_package.ps1`은 별도 레거시 포장 스크립트이며 현행 실행 파일·manifest 검증을 대체하지 않습니다.

이번 그림 안내의 소스는 `개발소스/docs/visual-guides/한눈에_사용안내.html`, 고객 전달물은 `개발소스/한눈에_사용안내.pdf`입니다. 재사용 프롬프트는 `개발소스/docs/VISUAL_GUIDE_PROMPTS.md`에 있습니다.

현행 릴리스 게이트는 PDF와 `README_먼저읽기.txt`, `사용안내.txt`를 소스 루트에서 고객용 실행폴더와 상위 최종 폴더로 복사하고 SHA-256이 같은지 확인한 뒤 고객 manifest를 다시 생성합니다. 기존 manifest가 있는 고객 폴더에 안내 파일만 수동 추가하면 추가·변경 파일 검증에 실패하므로, 실제 배포는 기존 릴리스 체크리스트를 따릅니다.

소스 문서 수정만으로 기존 고객용 실행폴더가 갱신되지는 않습니다. 릴리스 게이트의 manifest 검증 대상은 `개발소스/고객용_실행폴더`입니다. 소스·상위 폴더에 남은 고객 manifest로 해당 작업 폴더를 점검하면 추가·변경 파일로 실패할 수 있으므로, 그 결과를 고객 배포본 검증으로 간주하지 않습니다.

시각 안내는 고객 폴더에 PDF로 전달합니다. HTML 원본은 개발 문서에 두고, 고객 배포의 HTML 금지 규칙을 유지합니다. PDF는 패키지 폴더에서 직접 열며, 프로그램의 `설정 > 빠른 사용안내 열기`는 기존 텍스트 안내를 계속 엽니다.

## 실행 파일을 바꾸지 않는 안내 갱신

검증된 기존 고객 폴더의 안내만 갱신할 때는 `개발소스/안내_갱신본_만들기.cmd`를 사용합니다. 기본 실행은 쓰기 없는 점검이며 `--apply`를 지정해야 새 고객 폴더 복사본을 만듭니다. 기존 폴더는 보관하고, EXE 빌드 기록·버전정보·고객 데이터는 그대로 유지합니다. 상세 명령과 검증 범위는 `개발소스/docs/GUIDE_PACKAGE_UPDATE.md`에 있습니다.

## 레거시 포장 스크립트 생성 명령

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\build_customer_package.ps1
```

샘플 엑셀까지 포함하려면 아래처럼 실행합니다.

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\build_customer_package.ps1 -IncludeSampleWorkbooks
```

## 레거시 스크립트의 포함 파일

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

## 레거시 스크립트의 제외 항목

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
