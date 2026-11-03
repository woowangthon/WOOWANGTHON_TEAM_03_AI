# src — 모델 코드

파일별 설명은 저장소 루트 README 의 "폴더 구조" 절에 있다. 모듈은 서로를 최상위 이름으로 import 하므로 `src` 를 경로에 두고 실행한다 (서비스와 도구 스크립트는 스스로 경로를 넣는다).

```powershell
# 작업 폴더(저장소 루트)에서. Ollama 에 qwen3:30b-a3b-instruct-2507-q4_K_M, tev1-cpu, bge-m3-cpu 가 있어야 한다
$env:MODEL_API_KEYS = "<키>"
.venv\Scripts\python.exe src\server.py --port 8010                  # 모델 서비스
.venv\Scripts\python.exe src\tools\server_check.py                  # 서비스 점검 (서버를 직접 띄움)
.venv\Scripts\python.exe src\tools\accept_run.py src\data\accept\TEST-01.json   # 수락 검사
.venv\Scripts\python.exe src\eval.py --no-llm                       # 규칙만 평가 (Ollama 없이)
.venv\Scripts\python.exe -m pytest -q                               # 순수 함수 단위 테스트 (Ollama 없이, 1초)
```

백엔드가 쓰는 경로와 응답 형식은 `docs/모델 서비스 API v1 (2026-11-03).md`.
