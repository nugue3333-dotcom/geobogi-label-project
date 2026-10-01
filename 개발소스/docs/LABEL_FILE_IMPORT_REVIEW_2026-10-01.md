# 다른 라벨 프로그램 도안 가져오기 검토 보고서

- 확인일: 2026-10-01 KST
- 이번 UI 배포 버전: 2026.10.01.01

## 1. 유진디스컴 파일의 실제 실패 원인

바탕화면 `유진디스컴.png`는 46,311바이트이며 파일 시작에 `Bar Tender Format File`이 들어 있다. Pillow에서 PNG 이미지로 열 수 없었다. 이미지가 아니라 확장자가 변경된 BarTender 원본 파일이다. 따라서 이 사례는 OCR 정확도 문제가 아니다.

원본을 변경하지 않고 `유진디스컴_원본복원.btw` 복사본을 만들었다. 두 파일의 SHA-256은 `ec127f9695d87f3b9c5743610a9b75acd60b2d6211518a92c5e0f3156e8beed1`로 같다. 이 복사본은 파일 형식을 복원한 것이며 이미지로 변환한 결과는 아니다. 사용자 도안 내용이나 파일 자체를 외부 서비스에 업로드하지 않았다.

이 PC에서 확인한 프로그램은 BarTender 2016 R2, 파일 버전 11.0.2.3056이다. 로컬 쓰기 가능한 COM 캐시로 재시도했지만 `BarTender.Application` 생성이 `0x80080005 / 서버 실행이 실패했습니다`로 실패했다. 실제 이미지 내보내기와 이 도안의 해당 버전 호환성은 확인하지 못했다. 원본 파일이 생성된 정확한 BarTender 버전·에디션은 아직 알 수 없다.

### 바로 사용할 복구 절차

1. 도안을 작성한 버전의 BarTender에서 복원한 `.btw`를 연다.
2. 라벨 1장과 실제 데이터를 표시한다. 파일 이름만 `.png`로 바꾸지 않는다.
3. 프로그램의 실제 이미지 내보내기 또는 인쇄 미리보기 저장을 사용한다. 가능하면 흰 배경, 라벨 1장, 용지 크기 일치, 충분한 해상도를 선택한다. 300dpi를 시작점으로 사용할 수 있지만 인식 성공을 보장하지 않는다.
4. 이미지 뷰어에서 실제로 열리는지 확인한 뒤 채움랩의 도안 불러오기 → 도안 적용 → 인식 값 검토를 사용한다.
5. 전체 값을 대조한 후 전체 값 확인을 누른다. DB 열·바코드 종류·용지 설정을 연결하고 첫 장 실물을 출력·스캔한다.

원본에 맞는 프로그램에서 열리지 않으면 생성 버전 확인과 해당 프로그램 복구가 먼저다. 호환되지 않는 원본을 이름 변경이나 OCR로 읽을 수는 없다.

## 2. 권장 가져오기 방식

이미지에는 글자·선·바코드 모양이 남지만 객체 종류, DB 연결, 수식, 날짜·일련번호 규칙이 남지 않는다. 이미지 인식은 재작성 보조 수단이다. 편집 가능한 도안 이전에는 구조 데이터와 데이터 연결 정보를 함께 전달하는 방식이 적합하다.

| 원본 프로그램/파일 | 현실적인 경로 | 보존 가능 범위와 제한 |
| --- | --- | --- |
| BarTender `.btw` | 설치된 정식 프로그램의 ActiveX/SDK로 객체를 읽어 채움랩 형식으로 변환 | 공식 DesignObject에는 종류·값·위치·크기·글꼴·회전 등이 있다. 채움랩이 표현하는 개체부터 변환할 수 있다는 개발안이다. Automation 계열 에디션 등 API 사용 조건과 실제 버전별 타입·단위를 검증해야 한다. 이번 배포에 직접 변환기는 없다. |
| BarTender 이미지 출력 | 공식 `Format.ExportToFile` 또는 BTXML의 `ExportPrintPreviewToImage` | 실제 이미지 생성 기능이다. BTXML은 DPI·배경·여백·테두리를 지정할 수 있다. 여러 라벨이 한 페이지에 있으면 이미지도 여러 라벨을 포함할 수 있다. 이미지로는 수식과 DB 연결을 복구할 수 없다. |
| NiceLabel 원본 | 원본 프로그램에서 미리보기 + Get Label Information/변수 XML 추출 | 공식 정보 XML은 라벨 크기·프린터·변수와 속성을 제공한다. 모든 객체 좌표와 완전한 도안을 제공한다는 근거로 사용할 수는 없다. 레이아웃 재작성 또는 별도 SDK 검증이 필요하다. |
| ZebraDesigner `.lbl`/`.nlbl` | 원본 프로그램에서 PRN/프린터 명령으로 내보내기 | 버전에 따라 원본 형식이 다르다. PRN 출력 경로가 있으며, 실제 파일 언어를 판별한 뒤 ZPL 등 지원 명령에 한해 파서를 만드는 개발안이다. 비트맵 처리된 글자는 원래 텍스트·글꼴로 되돌릴 수 없다. |
| DYMO | 공식 SDK/Framework의 label XML 사용 | 공식 API가 XML 내용을 로드한다. 공개 샘플과 실제 XML 버전에 맞춰 지원 객체를 매핑하는 방식을 검토할 수 있다. 모든 DYMO 형식이 같은 구조라고 가정하지 않는다. |
| LABELVIEW/CODESOFT/LABEL MATRIX | 원본 프로그램의 공식 내보내기/자동화, 제조사 변환 서비스 활용 | TEKLYNX는 다른 프로그램 도안을 자사 제품으로 변환하는 서비스를 제공한다. 그 기능이 채움랩으로 내보내기를 지원한다는 뜻은 아니다. 사용 버전의 API·내보내기 결과를 확보한 뒤 범위를 정해야 한다. |
| 공통 PDF/SVG/이미지 | 고정 배경을 보존하고 가변 글자·바코드를 다시 연결 | 시각적 형태 보존에 유리한 개발안이다. PDF/SVG 지원은 이번 배포에 추가하지 않았다. 복잡한 폰트·회전·단위·클리핑과 다중 페이지 검증이 필요하다. |

## 3. 구현 우선순위 제안

1. **실제 파일 형식 검사**: 이번에 BarTender 파일을 PNG로 잘못 지정한 경우를 구분해 올바른 내보내기를 안내했다. 진짜 투명 PNG의 인식은 흰 배경으로 합성하도록 개선했다.
2. **BarTender 구조 추출 어댑터**: 고객이 실제 쓰는 버전의 정식 엔진에서 텍스트·바코드·선·박스·이미지·라벨 크기를 읽어 `.gblabel`/`.gbproject`로 저장한다. 지원하지 않는 개체·수식은 변환 결과표에서 알리고, 외부 스크립트와 DB 작업은 자동 실행하지 않는다.
3. **데이터 연결 재지정 화면**: 원본 변수와 고객 엑셀 열을 매핑하고 빈 값·앞자리 0·바코드 종류를 검증한다. 미지원 항목을 숨기고 성공으로 표시하지 않는다.
4. **ZPL/공개 XML 등 범위가 명확한 형식**: 실제 원본 샘플과 정식 명세가 확보된 형식부터 추가한다. `.lbl`이라는 확장자만 보고 동일한 파일로 간주하지 않는다.
5. **원본 대조 승인**: 변환 전후 미리보기, 누락 개체 목록, 라벨 크기·인식 값 비교 후 첫 장 1D/2D 인쇄·스캔으로 완료한다.

완료 기준은 샘플 원본별 객체·위치·값 대조, 재저장·재열기, 엑셀 재연결, 미지원 항목 보고, 취소·오류 시 원본 유지, 인쇄파일 검증과 실제 장비 테스트다. 모든 상용 프로그램 원본 파일을 설치 없이 직접 읽는 범용 변환기를 약속하지 않는다.

## 4. 이번 UI 수정

- 인식 값 검토의 **전체 값 확인**: 선택한 입력란의 수정까지 함께 적용한다. 빈 값·임시 바코드가 있으면 전체를 적용하지 않아 부분 승인으로 남지 않는다.
- 오른쪽 **상품 DB 전용**: 개체 속성 전환과 개체 편집 버튼을 제거했다. DB 연결·엑셀 새로고침·DB 열 지정·현재 행 값은 유지한다. 개체 편집은 캔버스 더블클릭으로 연다.
- 왼쪽 정밀 편집 메뉴 제거. 상단에 **좌우 가운데 정렬**, **상하 가운데 정렬**을 배치했다. 다중 선택은 상대 위치를 유지하고 잠긴 개체는 이동하지 않는다.
- 실제 `.btw`를 이미지로 오인한 경우 구체적인 오류와 복구 방법을 안내한다. 일반 이미지 가져오기는 계속 지원한다.

## 5. 확인한 공식 자료

- [BarTender DesignObject 객체 속성·에디션 조건](https://help.seagullscientific.com/2016/ja/Subsystems/ActiveX/Content/DesignObject_Object.htm)
- [BarTender Format.ExportToFile](https://help.seagullscientific.com/2016/en/Subsystems/ActiveX/Content/ExportToFile_Method.htm)
- [BarTender BTXML 실제 이미지 내보내기](https://help.seagullscientific.com/2016/en/Subsystems/BTXML/Content/ExportPreviewCommand_Tag.htm)
- [NiceLabel Get Label Information](https://help.nicelabel.com/hc/en-001/articles/360020970737-Other)
- [NiceLabel 변수 XML 명세](https://help.nicelabel.com/hc/en-001/articles/4406629681169-Variables-Export-File-Definition)
- [ZebraDesigner 형식 안내](https://www.zebra.com/content/dam/zebra_dam/en/fact-sheet/zebra-designer-fact-sheet-en-us.pdf)
- [ZebraDesigner PRN 생성](https://support.zebra.com/article/000020485)
- [DYMO 공식 SDK 샘플](https://github.com/dymosoftware/DCD-SDK-Sample)
- [TEKLYNX 도안 변환 서비스](https://www.teklynx.com/en/support/professional-services)
