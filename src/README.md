# src — 모델 코드

모듈은 서로를 최상위 이름으로 import 하므로 `src` 를 경로에 두고 실행한다 (서비스와 도구 스크립트는 스스로 경로를 넣는다). 흐름도 번호는 저장소 루트 README 의 그림 번호다.

## 파일별 설명

```
src/
├─ common.py                     경로, Ollama 호출(반드시 127.0.0.1), Span 자료형, 라벨 7종과 예비 라벨 other
├─ extract.py                    PDF → 글자 (PyMuPDF). 글자를 고치지 않고 쪽 사이 빈 줄 하나. 흐름도 ①
├─ detect_rules.py               정규식 26개(연락처·번호·사업명·금액·사람) + 사전(회사명·사업명) 즉시 탐지. 흐름도 ②
├─ ner_detect.py                 공개 한국어 NER(atonlee/koelectra-ko-pii-ner, CPU)로 사람 이름만. 흐름도 ②
├─ detect_llm.py                 Ollama 30B(qwen3:30b-a3b-instruct) JSON 스키마 구간 추출, 원문 포함 검사. 흐름도 2-1
├─ detect.py                     즉시 경로와 30B 결과 병합·전파·다듬기, 지시 삽입 문장 지우기, 구분자 감싸기, 긴 글 분할. detect(text)
├─ route.py                      tev1(/v1/systemone)에 기준 문구를 주고 사내·외부·차단 확률. 글이 길면 앞 6,000자만 보낸다. 흐름도 3.1 → ③
├─ decide.py                     결정 규칙: 개인정보 묶음·통째 유출 차단, 내부 전용 사내 강제, 애매 판정, 승인 카드 필요 여부. 흐름도 ④
├─ mask.py                       자리표 가림, 등급 정책(1 항상·2 이름 토글·3 비가림), 복원, 외부 안내문. 흐름도 ⑤
├─ answer_external.py            Anthropic API(claude-sonnet-5-5) 호출: 전송 직전 유출 검사, 답변 자리표 복원, 거부·비용 추정. 흐름도 4.2
├─ server.py                     FastAPI 모델 서비스(8010): /detect/instant /analyze /mask /restore /answer_local /answer_external /embed /dict/reload. 흐름도의 연구실 PC 상자 전체
├─ eval.py                       평가 세트 재현율·오탐·민감 판정 정확도·지연 표
├─ data/
│  ├─ samples.jsonl              기본 평가 세트 10건 (text, 정답 spans, 정답 route)
│  ├─ candidates/                밤 배치가 만든 후보·공격·영어·사내 세트. 정답 검토 전 원본(*_before_review_*, *_raw)은 archive/
│  ├─ demo/demo_docs_v1.jsonl    시연 문서 6건 D1~D6 (경로별 기대 결정, 등급별 정답 구간)
│  ├─ accept/                    실제 형태 수락 검사 TEST-01: 입력 PDF(츄러스공업, 가상 데이터), 정답표 TEST-01.json, 추출 글자 TEST-01.txt
│  └─ dict/                      companies.txt, projects.txt 사전. 한 줄에 하나, 세로줄(|)로 별칭
├─ results/                      평가·점검 스크립트가 결과 md/json 을 쓰는 곳 (eval_*, decide_check_*, route_check_*, demo_run_*,
│                                night*/, gold_review_*, accept_*, server_check_*, external_check_*). 지금은 비어 있다.
│                                이전 결과는 모델을 고치기 전 것이라 지웠고, 최종 모델로 다시 평가한 뒤 채운다
└─ tools/
   ├─ server_check.py            서비스 점검 17항목: 인증, 즉시 탐지 일치, 결정, 복원, 동시 호출, TEST-01, 사내 답변, 임베딩, 사전 재적재 (--external 이면 외부 호출까지 18항목)
   ├─ external_check.py          외부 경로 점검: smoke 1회 + D3·D4·D6·TEST-01 을 가림 → Anthropic → 복원, 자리표 유지·유출·비용
   ├─ accept_run.py              수락 검사: PDF + 정답표 → 탐지 → 경로 → 결정 → 가림. 사전 없음/등록 × 이름 토글 끔/켬
   ├─ demo_run.py                시연 6건을 파이프라인에 넣어 기대 경로와 등급별 적중 비교
   ├─ decide_check.py            결정 규칙 회귀: 세트별 정답 경로·차단 비교
   ├─ route_check.py             tev1 기준 문구 변형(v1~v5) 비교
   ├─ gold_review.py             정답과 탐지기가 다른 곳만 모은 검토 목록
   ├─ apply_gold_fixes.py        정답 검토 판정을 세트에 반영하고 변경 로그 작성
   ├─ clean_candidates.py        후보 세트 기계 정리(중복·형식)
   ├─ ner_probe.py               NER 모델 로딩·라벨·속도 확인
   ├─ night_run.py ~ night_run4.py  밤 배치 실험: 라우팅 반복, 지연, few-shot 효과, 동시 호출, 긴 글, 프롬프트 3종, NER, RAG 게이트, M 모드.
   │                             일회성 실험 기록이다 (M 모드는 기각 뒤 코드에서 뺐으므로 night_run4 는 재현되지 않는다)
   └─ md2pdf.py                  md → PDF (Word COM). 문서의 공유용 PDF 를 만들 때 쓴다
```

## 실행

```powershell
# 작업 폴더(저장소 루트)에서. Ollama 에 qwen3:30b-a3b-instruct-2507-q4_K_M, tev1-cpu, bge-m3-cpu 가 있어야 한다
$env:MODEL_API_KEYS = "<키>"
.venv\Scripts\python.exe src\server.py --port 8010                  # 모델 서비스
.venv\Scripts\python.exe src\tools\server_check.py                  # 서비스 점검 (서버를 직접 띄움)
.venv\Scripts\python.exe src\tools\accept_run.py src\data\accept\TEST-01.json   # 수락 검사
.venv\Scripts\python.exe src\eval.py --no-llm                       # 규칙만 평가 (Ollama 없이)
.venv\Scripts\python.exe -m pytest -q                               # 순수 함수 단위 테스트 (Ollama 없이)
```

백엔드가 쓰는 경로와 응답 형식은 `docs/모델 서비스 API v1 (2026-11-03).md`.
