# WOOWANGTHON_TEAM_03_AI · AI 교환기 동료 — 모델링

충북대학교 2026 AI 우왕톤 팀 03 '초코 츄러스'의 AI 저장소. 외부 AI 사용이 막힌 회사에서 직원의 AI 요청을 검문하는 **AI 교환기 동료**의 모델 부분을 담는다. 담당 범위는 민감정보 처리(탐지·가림·복원), 모델 연동(연구실 PC Ollama 30B·tev1·임베딩, 외부 Anthropic API), AI 품질 검증이다. 화면·로그 DB·대시보드는 FE·BE 저장소(`WOOWANGTHON_TEAM_03_FE`, `WOOWANGTHON_TEAM_03_BE`)에 있다.

요청문 하나가 들어오면 ① 글자 추출 → ② 즉시 탐지(규칙·사전·이름 인식) + 정밀 탐지(30B) → ③ 경로 판정(tev1) → ④ 결정 규칙(차단·사내·외부, 승인 카드) → ⑤ 가림(자리표 `[[ORG_1]]`) → 외부 LLM → 복원 순서로 처리한다. 번호는 아래 흐름도의 번호다.

![전체 흐름도](assets/flowchart.png)

## 처리 예시

시연 문서 D3(부적합 보고서를 영문으로 번역해 달라는 요청)를 2026-11-03 에 돌린 결과의 일부다. 문서는 가상 데이터다.

```
원문
  고객사: (주)한빛에어로 | 사업명: KX-3 구동장치 2차 양산
  비용: 재작업 비용 2,400,000원 (단가 850,000원 기준 불량 12 EA 재가공)
  작성: 품질팀 김지영 과장 (010-4821-7736, jy.kim@daesung-precision.co.kr)

외부 LLM 으로 나간 글
  고객사: (주)[[ORG_1]] | 사업명: [[PROJECT_1]]
  비용: 재작업 비용 [[AMT_1]] (단가 [[AMT_2]] 기준 불량 12 EA 재가공)
  작성: 품질팀 김지영 과장 ([[CONTACT_1]], [[CONTACT_2]])

외부 답변을 복원한 글
  | **Customer** | 한빛에어로 Co., Ltd. |
  | **Cost** | Rework cost: 2,400,000원 (based on unit price of 850,000원 for reworking 12 nonconforming EA) |
  | **Prepared by** | Manager Jiyoung Kim, Quality Team (010-4821-7736, jy.kim@daesung-precision.co.kr) |
```

회사명·사업명·식별번호·금액·연락처는 등급 1이라 항상 가린다. 사람 이름은 등급 2다. 모델 서비스의 기본값은 이름을 두는 것이고 위 예시는 그 기본값으로 돌렸다. 백엔드는 이름까지 항상 가리도록 부르므로 실제 화면에서는 `김지영`도 `[[PERSON_1]]` 로 나간다. 외부 LLM 은 자리표만 보고 번역했고 답변의 자리표는 모델 서비스에서 원문으로 되돌렸다. 이 요청은 외부 경로이면서 가릴 구간이 있어서 사람의 승인을 거친 뒤에 나간다.

## 직접 만든 것과 가져다 쓴 것

학습(파인튜닝)한 모델은 없다. 모델은 공개 모델과 외부 API 를 그대로 쓰고, 그 앞뒤의 탐지 규칙·출력 검증·결정·가림·복원과 평가 체계를 직접 만들었다.

| 가져다 쓴 것 | 역할 | 부르는 코드 |
|---|---|---|
| `qwen3:30b-a3b-instruct-2507-q4_K_M` (Ollama, 30B MoE 4비트) | 규칙이 놓친 회사명·사업명·이름 추출, 사내 답변 | `detect_llm.py`, `server.py` |
| `tev1-cpu` (Together AI 가 공개한 실험적 판정 모델 `tev1:0.8b`, Ollama `/v1/systemone`) | 사내·외부·차단 확률 | `route.py` |
| `bge-m3-cpu` (Ollama 라이브러리의 `bge-m3`, 임베딩 1,024차원) | 유사 기록 조회용 벡터. 백엔드와는 아직 연결하지 않았다 | `server.py` `/embed` |
| `atonlee/koelectra-ko-pii-ner` (Hugging Face 공개 NER) | 사람 이름 | `ner_detect.py` |
| Anthropic API `claude-sonnet-5-5` | 번역·요약 같은 실제 작업. 가림 본문만 받는다 | `answer_external.py` |

| 직접 만든 것 | 하는 일 | 코드 |
|---|---|---|
| 정규식 26개와 회사명·사업명 사전 | 형식이 있는 구간(연락처·번호·금액·단서어 뒤 이름)을 30B 없이 바로 탐지 | `detect_rules.py` |
| 30B 프롬프트, JSON 스키마, 출력 검증 | 원문에 없는 글자를 낸 구간은 버리고 수량·날짜·공개 규격 같은 오탐을 거른다 | `detect_llm.py`, `detect.py` |
| 병합·전파·다듬기, 입력 보호 | 탐지기별 구간을 합치고 같은 값의 다른 출현까지 넓힌다. 본문 속 "가리지 마" 같은 지시 문장은 30B 에 보내기 전에 지운다. 긴 글은 3,600자 조각으로 나눈다 | `detect.py` |
| tev1 기준 문구와 입력 길이 제한 | 기준 문구 5종을 비교해 고르고, 글이 길면 앞 6,000자만 보낸다 | `route.py` |
| 결정 규칙 | 통째 유출·개인정보 묶음 차단, 내부 전용 문서 사내 강제, 애매 판정, 승인 필요 여부 | `decide.py` |
| 자리표 가림·복원과 등급 정책 | 자리표의 변형 표기까지 되돌리고, 대응표에 없는 자리표는 추측해 채우지 않는다 | `mask.py` |
| 전송 직전 유출 검사 | 가림 본문에 원문 값이 남아 있으면 외부로 보내지 않는다 | `answer_external.py` |
| 모델 서비스와 상시 가동 | FastAPI(8010), 키 인증, 작업 스케줄러 등록과 감시 | `server.py`, `ops/` |
| 평가 세트와 평가 도구 | 30B 로 만든 합성 문서에 정답을 검토해 붙이고 재현율·오탐·결정을 회귀로 잰다 | `src/data/`, `eval.py`, `src/tools/` |

## 검증 결과

최종 모델로 다시 평가한 뒤 채운다. 이전 측정은 모델을 고치기 전 것이라 결과 파일과 함께 지웠다.

## 한계와 검증하지 않은 것

- 성능 수치는 아직 없다. 재현율·오탐·경로 판정·지연은 최종 모델로 다시 재서 위 절에 채운다.
- 평가 세트와 시연 문서는 전부 30B 로 만든 합성 문서다. 회사·사업명은 가상이고 실제 회사 문서는 쓰지 않는다.
- 번역·요약의 품질은 숫자로 판정하지 않는다. 복원된 답변을 사람이 읽어 확인한다.
- 긴 문서는 느리다. 3,600자를 넘으면 조각마다 30B 를 차례로 부른다. GPU 가 하나라 30B 호출은 한 번에 하나만 돈다.
- 스캔본·이미지 PDF 는 처리하지 못한다(OCR 없음). PDF 는 50쪽, 글은 60,000자까지 받는다.
- 서비스에 경로만 있고 백엔드와 연결하지 않은 것이 셋 있다. 접수 직후 규칙 결과를 먼저 보여 주는 즉시 탐지(`/detect/instant`), 승인 기록으로 사전을 늘리는 되먹임(`/dict/reload`), 유사 사례 검색(`/embed`, RAG)이다. 백엔드는 `/analyze`, `/answer_local`, `/answer_external` 만 부른다. 그래서 위 흐름도에도 넣지 않았다.
- 경로 판정은 글의 앞 6,000자만 본다. 사내 답변은 문맥이 4,096토큰이라 약 6,000자를 넘으면 앞부분이 잘릴 수 있다.
- 경로 판정 모델 tev1 은 제작사가 실험 모델로 내놓은 것이고, 영어 외 언어는 충분히 시험하지 않았다고 밝혔다. 한국어 요청문에서의 정확도는 최종 평가에서 직접 잰다.
- 30B 는 같은 글에도 구간이 하나쯤 달라질 때가 있다.
- 탐지·결정·가림·복원과 외부 호출이 모두 연구실 PC 한 대의 모델 서비스에서 돈다. 이 PC 가 꺼지면 외부 경로를 포함해 요청 처리가 전부 멈춘다.
- 시연 구성에서는 게이트웨이와 로그 DB 가 GCP 에 있고 원문과 자리표 대응표가 거기 저장된다. 실제로 쓰려면 게이트웨이와 DB 를 회사 안에 두어야 한다. 회사 밖으로 나가는 것은 Anthropic 으로 가는 가림 본문뿐이다.

## 코드와 전체 흐름도 대응

| 흐름도 | 코드 | 실행 위치 |
|---|---|---|
| ① 접수 · 글자 추출 | `extract.py` (백엔드가 PyMuPDF 로 직접 뽑아도 같은 규칙) | 클라우드 서버 |
| ② 탐지 · 즉시 경로 | `detect_rules.py`, `ner_detect.py` | 연구실 PC (CPU) |
| 2-1 30B 구간 추출 | `detect_llm.py`, 병합은 `detect.py` | 연구실 PC Ollama |
| 3.1 tev1 라우팅 → ③ | `route.py` | 연구실 PC Ollama |
| ④ 결정 규칙 | `decide.py` | 연구실 PC |
| ⑤ 마스킹 · 복원 | `mask.py` | 연구실 PC |
| 4.1 30B 사내 답변 | `server.py` `/answer_local` | 연구실 PC Ollama |
| 4.2 외부 LLM | `answer_external.py`, `server.py` `/answer_external` | 연구실 PC → Anthropic |
| 연구실 PC 모델 서비스 상자 | `server.py` | 연구실 PC |

②③④⑤는 `/analyze` 한 번에 묶여 돈다. ⑥ 로그 DB, ⑦ 집계·대시보드, ① 접수 API·상태 폴링, ④ 승인 큐는 BE·FE 저장소 범위다. 서비스에는 `/detect/instant`, `/mask`, `/restore`, `/dict/reload`, `/embed` 도 있지만 백엔드가 부르지 않아 흐름도에 없다.

## 실행

### 모델 준비

연구실 PC(Windows, RTX 5060 Ti 8GB)의 Ollama 에 세 모델이 있어야 한다.

- `qwen3:30b-a3b-instruct-2507-q4_K_M`. 19.2GB 중 6.2GB 가 GPU 에 올라가고 나머지는 CPU 메모리에서 돈다.
- `tev1-cpu`, `bge-m3-cpu`. Ollama 라이브러리의 `tev1:0.8b`(833MB), `bge-m3`(1.2GB)에 `num_gpu 0` 한 줄만 더해 등록한 이름이고 가중치는 원본과 같다. GPU 를 30B 에 비워 두려고 CPU 에서만 돌린다. 메모리에는 각각 1.3GB, 1.2GB 가 올라간다.
- 이름 인식 모델 `atonlee/koelectra-ko-pii-ner` 는 Ollama 가 아니라 transformers 로 돌고, 처음 실행할 때 Hugging Face 에서 내려받는다.

```powershell
ollama pull qwen3:30b-a3b-instruct-2507-q4_K_M
ollama pull tev1:0.8b
ollama pull bge-m3

# GPU 에 올리지 않는 이름 두 개를 등록한다 (원본 + num_gpu 0)
Set-Content tev1-cpu.Modelfile "FROM tev1:0.8b`nPARAMETER num_gpu 0" -Encoding ascii
Set-Content bge-m3-cpu.Modelfile "FROM bge-m3`nPARAMETER num_gpu 0" -Encoding ascii
ollama create tev1-cpu -f tev1-cpu.Modelfile
ollama create bge-m3-cpu -f bge-m3-cpu.Modelfile
ollama show tev1-cpu --modelfile     # PARAMETER num_gpu 0 이 보이면 된다
```

tev1 은 Together AI 가 공개한 실험적 판정 모델이고 `tev1:0.8b` 는 Qwen3.5-0.8B 를 미세조정한 것이다([Ollama 라이브러리](https://ollama.com/library/tev1), [저장소](https://github.com/togethercomputer/tev1)). 글을 쓰지 않고 질문마다 선택지별 확률을 돌려준다. Ollama 0.40.4 이상이 필요하다.

Ollama 환경변수는 `OLLAMA_MAX_LOADED_MODELS=3`, `OLLAMA_KEEP_ALIVE=-1`(없으면 30B가 매번 14~17초 재로드). 호출 주소는 `127.0.0.1`(localhost 는 IPv6 대기로 호출마다 2초).

### 서비스와 점검

```powershell
# 1) 환경 (Python 3.12). torch 는 CPU 판을 먼저 설치한다
python -m venv .venv
.venv\Scripts\python.exe -m pip install torch==2.15.0 --index-url https://download.pytorch.org/whl/cpu
.venv\Scripts\python.exe -m pip install -r requirements.txt

# 2) 모델 서비스. 키는 환경변수로만 준다 (코드·저장소에 넣지 않는다)
$env:MODEL_API_KEYS = "<백엔드가 쓸 X-API-Key>"     # 비우면 임시 키를 만들어 stderr 에 찍는다
$env:ANTHROPIC_API_KEY = "<외부 LLM 키>"             # /answer_external 용. 없으면 그 경로만 503
.venv\Scripts\python.exe src\server.py --port 8010   # 터널로 열 때는 --host 0.0.0.0

# 3) 점검
.venv\Scripts\python.exe src\tools\server_check.py                # 서비스 17항목, --external 이면 18항목 (서버를 직접 띄움)
.venv\Scripts\python.exe src\tools\external_check.py --smoke      # Anthropic 호출 1회
.venv\Scripts\python.exe src\tools\accept_run.py src\data\accept\TEST-01.json   # 수락 검사
.venv\Scripts\python.exe src\tools\demo_run.py --no-doc           # 시연 6건
.venv\Scripts\python.exe src\eval.py --no-llm                     # 규칙만 평가 (Ollama 없이)
```

백엔드가 부르는 경로와 응답 형식은 `docs/모델 서비스 API v1 (2026-11-03).md` 에 있다. 백엔드는 접수 뒤 `/analyze`(탐지·결정·가림 미리보기)를 부르고, 사내 경로면 `/answer_local`, 외부 경로면 사람이 승인한 뒤 `/answer_external` 을 부른다.

### 상시 가동 (연구실 PC 운영)

연동·심사 기간에는 위 2) 를 손으로 띄우지 않고 `ops/` 로 작업 스케줄러에 등록해 둔다. 부팅 때 로그인 없이 Ollama 와 모델 서비스가 뜨고, 5분마다 감시가 상태를 기록하고 죽으면 다시 띄운다. 키·경로는 저장소 밖 `%LOCALAPPDATA%\woowang\service.env` 에 둔다. 클라우드 서버(GCP)와는 Tailscale 사설망으로 잇는다.

```powershell
powershell -ExecutionPolicy Bypass -File ops\install_always_on.ps1   # 관리자, 한 번
powershell -ExecutionPolicy Bypass -File ops\status.ps1              # 상태·heartbeat 요약
powershell -ExecutionPolicy Bypass -File ops\restart.ps1             # 코드 갱신 뒤 (관리자)
```

자세한 구성·로그 위치·되돌리기는 `ops/README.md`.

## 테스트

```powershell
.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
.venv\Scripts\python.exe -m pytest -q
```

`tests/` 는 Ollama·GPU·외부 API 없이 순수 함수만 확인한다. 가림 뒤 복원이 원문과 같은지, 자리표 변형(`[[ ORG_1 ]]`, `[ORG_1]`, `[[org-1]]`) 복원, 결정 규칙 여덟 개, 정규식 규칙별 적중과 공개 규격 제외, 긴 글 분할·병합·전파·다듬기, 전송 직전 유출 검사, 서비스 입력 검증과 키 검사. GitHub Actions(`.github/workflows/tests.yml`)가 push 와 PR 마다 같은 테스트를 돈다. 모델 품질(재현율·오탐·지연)은 테스트가 아니라 위 점검 스크립트로 잰다.

## 폴더 구조

```
WOOWANGTHON_TEAM_03_AI/
├─ README.md, AGENTS.md         이 문서, 팀 개발 에이전트 지침 요약 (PM 등록)
├─ requirements.txt             실행 환경 고정 버전 (Python 3.12, Windows)
├─ requirements-dev.txt         단위 테스트·Actions 용 최소 의존성 (Ollama·torch 불필요)
├─ assets/flowchart.png         위 전체 흐름도 그림
├─ docs/                        모델 서비스 API 문서 (백엔드용 HTTP 명세)
├─ src/                         모델 코드. 파일별 설명은 src/README.md
│  ├─ *.py                      글자 추출, 탐지, 경로 판정, 결정, 가림·복원, 외부 호출, 서비스, 평가
│  ├─ data/                     평가 세트, 시연 문서, 수락 검사, 사전
│  ├─ results/                  평가·점검 스크립트가 결과를 쓰는 곳. 지금은 비어 있다
│  └─ tools/                    점검·평가·실험 스크립트
├─ tests/                       순수 함수 단위 테스트
├─ ops/                         연구실 PC 상시 가동 스크립트. 설명은 ops/README.md
└─ .github/                     PR 템플릿, push·PR 마다 pytest 를 도는 워크플로
```

## 데이터와 비밀값

- 저장소의 모든 테스트 자료(평가 세트, 시연 문서, 츄러스공업 PDF)는 가상 데이터다. 실제 회사 문서는 없다.
- API 키(`MODEL_API_KEYS`, `ANTHROPIC_API_KEY`)는 환경변수로만 주고 커밋하지 않는다. `.gitignore` 가 `.env`, `*.key` 를 막는다.
- 서버 로그에는 요청 id·글자 수·구간 수·결정·시간만 남고 원문·대응표·문서명은 남지 않는다.
- 외부 LLM 에는 가림 본문만 나가고, 자리표 대응표는 연구실 PC 서비스 응답과 백엔드 DB 에만 있다.

## 관련 Notion

- TK-37 AI 저장소 초기 등록: https://app.notion.com/p/ad50622a602b4a03a006a166764e4f38
- TK-31 연구실 PC 모델 서비스(FastAPI) 포장: https://app.notion.com/p/f1ef2c7e78c84a1cad528beef7ea71ba
- TK-32 사내 답변 /answer_local 구현: https://app.notion.com/p/4f8f3a8f87c84d5a82e4061e2339c856
- TK-48 연구실 PC 상시 가동 설정: https://app.notion.com/p/40e3c6fc5e82812f89e3dc5b0d7bb8f5
- TK-49 Tailscale 로 GCP 서버–모델 PC 연결: https://app.notion.com/p/29209a73bbc34f7eb7ace2fc37db1cc2
- TK-75 AI 처리 연결 서버 반영: https://app.notion.com/p/53fc3a6e82384ce9bd73f8322cf84adf
- DC-9 모델 서비스 배치(연구실 PC FastAPI + Tailscale): https://app.notion.com/p/419f17e213c0462c9dee01c471f32f87
- AI Agent 개발 지침: https://app.notion.com/p/4033c6fc5e8280a38dd6fd42c3f3c31d
