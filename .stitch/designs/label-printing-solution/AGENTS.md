\# Codex-Hermes 작업 규칙



\## 역할 분리



\- Codex는 코드 수정, 파일 편집, 테스트 실행을 담당한다.

\- Hermes는 마케팅 구조, 카피, 사용자 관점, 웹페이지 기획, 섹션 구성, 보조 분석을 담당한다.

\- Hermes가 직접 파일을 수정하지 않는다.

\- 실제 파일 수정은 Codex만 한다.



\## Hermes 호출 방법



외부 기획, 마케팅 카피, 랜딩페이지 구조, 사용자 관점 분석이 필요하면 아래 명령을 실행한다.



```powershell

powershell -NoProfile -ExecutionPolicy Bypass -File .\\ask-hermes.ps1 "<질문>"

