# AI 교환기 모델링 — 탐지기 v0

외부 AI로 보내기 전에 가릴 민감 구간을 찾는 부분. 규칙(정규식·사전)과 로컬 30B(JSON 추출)를 합친다.

## 실행

집 PC에서 Ollama가 떠 있어야 한다 (`qwen3:30b-a3b-instruct-2507-q4_K_M`, `tev1-cpu`).

```powershell
# 작업 폴더(woowang)에서
.venv\Scripts\python.exe src\eval.py            # 규칙 / 30B / 혼합 비교, results/에 md·json 저장
.venv\Scripts\python.exe src\eval.py --no-llm   # 규칙만 (30B 호출 없음, 1초 안에 끝남)
.venv\Scripts\python.exe src\detect.py          # 예시 문장 1개 탐지
```

## 모델 서비스 (11-03)

백엔드가 HTTP로 부르는 서비스. 경로·형식은 프로젝트 루트 "모델 서비스 API v1 (2026-11-03).md" 참고.

```powershell
$env:MODEL_API_KEYS = "<키>"                     # 비우면 임시 키를 만들어 stderr에 찍는다
.venv\Scripts\python.exe src\server.py --port 8010
.venv\Scripts\python.exe src\tools\server_check.py   # 서버를 띄우고 시연 6건·TEST-01을 HTTP로 통과시키는 점검
```

## 파일

| 파일 | 역할 |
|---|---|
| `server.py` | FastAPI 모델 서비스: /health /status /detect/instant /analyze /mask /restore /answer_local /embed /dict/reload. X-API-Key 인증, 30B 호출은 LLM_LOCK으로 직렬 |
| `tools/server_check.py` | 서비스 배관 점검(인증·즉시 탐지 일치·결정·복원·동시 호출·TEST-01·사내 답변·임베딩·사전 재적재, `--external`이면 외부 호출까지) → results/server_check_*.md |
| `answer_external.py` | 외부 LLM 호출(Anthropic, 기본 claude-sonnet-5-5): 전송 직전 유출 검사, 답변 자리표 복원, 거부·대체 모델·토큰·비용 추정. 키는 환경변수 ANTHROPIC_API_KEY |
| `tools/external_check.py` | 외부 경로 점검: smoke 1회 + D3·D4·D6·TEST-01을 탐지→가림→외부→복원, 자리표 유지·복원·유출·비용 → results/external_check_*.md |
| `data/samples.jsonl` | 평가 샘플. `text`, 정답 `spans`(text, label), 정답 `route`(local/external) |
| `data/dict/companies.txt`, `projects.txt` | 회사명·사업명 사전. 한 줄에 하나 |
| `common.py` | 경로, Ollama 호출, `Span` 자료형, 라벨 목록 |
| `detect_rules.py` | 정규식(이메일, 전화, 사업자번호, 도면·품번·발주번호, 로트, 금액, 담당자 이름) + 사전 |
| `detect_llm.py` | 30B JSON 스키마 추출. 한국어 지시, label enum 강제, 원문에 없는 구간은 버림 |
| `detect.py` | 둘을 합쳐 `detect(text)` → spans, sensitive, timing |
| `eval.py` | 재현율·오탐·민감 판정 정확도·지연 표 |

## 라벨

`company` 회사명 · `project` 사업명 · `doc_no` 도면/품번/발주/로트 번호 · `price` 금액 · `person` 사람 · `contact` 전화/이메일 · `biz_no` 사업자/주민번호 · `other`

## 백엔드에서 쓰는 법

```python
import sys; sys.path.insert(0, "src")
from detect import detect
r = detect(text)              # 규칙 + 30B
r["sensitive"]                # True면 가림 필요
[(s.start, s.end, s.label) for s in r["spans"]]   # 가릴 구간 (문자 오프셋)
r["timing"]                   # rules_ms, llm_total_s ...
```

`detect(text, use_llm=False)`는 규칙만 돌려 즉시 반환한다. 화면에서 규칙 결과를 먼저 보여 주고 30B 결과를 뒤에 덧붙이는 2단계 표시에 쓴다.
