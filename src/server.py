"""모델 서비스: 집 PC에서 탐지·라우팅·결정·가림·복원을 HTTP로 내준다. (흐름도 ②③④⑤의 모델 부분 = 분석서 '집 PC 모델 서비스')

실행:  .venv\\Scripts\\python.exe src\\server.py [--host 127.0.0.1] [--port 8010]
       또는 src 폴더에서  uvicorn server:app --host 0.0.0.0 --port 8010
인증:  GET /health 를 뺀 모든 경로는 X-API-Key 헤더가 맞아야 한다. 키는 환경변수 MODEL_API_KEYS (쉼표로 여러 개).
       비어 있으면 시작할 때 임의 키를 만들어 stderr에 한 번 찍는다 (개발용. 키 없이 열리는 경우는 없다).
경로:
  GET  /health          {ok, service, version}. 키 없이. 터널·백엔드 헬스체크용
  GET  /status          Ollama 상주 모델, 사전 크기, NER 준비 여부, 처리 건수, 버전
  POST /detect/instant  {text | instruction+body} → 규칙·사전·NER 구간 (1~60ms). 접수 즉시 1차 카드
  POST /analyze         {text | instruction+body, policy, use_llm} → 탐지(30B 포함) ∥ 라우팅 → 결정 → 가림 묶음 (2차 카드)
  POST /mask            {text, spans, policy} → 가림 본문·대응표 (승인 카드에서 이름 토글을 바꿔 다시 가릴 때)
  POST /restore         {answer, mapping} → 외부 답변의 자리표를 원문으로
  POST /answer_local    {text | instruction+body} → 30B가 원문으로 답변 (사내 처리 4.1, 외부 미전송)
  POST /answer_external {masked, mapping} 또는 {text, spans, policy} → 가림 본문을 Anthropic API로 보내고 답변의 자리표를 복원 (4.2 외부)
                        키는 환경변수 ANTHROPIC_API_KEY. 없으면 503. 보내기 직전 원문 값이 가림 본문에 남아 있으면 409로 막는다
  POST /embed           {texts} → bge-m3 벡터 1024차원 (유사 기록 조회 ⑨)
  POST /dict/reload     {companies?, projects?} → 사전 파일 갱신·재적재 (학습 배치 ⑧)
원칙: 원문·대응표는 응답에만 담고 서버 로그에는 글자 수·결정·시간만 남긴다 (MT-3 보안 고문 조언). Ollama는 127.0.0.1로만 부른다.
GPU가 하나라 30B 호출(탐지·사내 답변)은 LLM_LOCK으로 한 번에 하나만 돈다. tev1·NER·임베딩은 CPU라 동시에 돈다.
"""
import argparse
import asyncio
import hashlib
import hmac
import json
import logging
import os
import secrets
import shutil
import sys
import threading
import time
import urllib.request
from contextlib import asynccontextmanager
from pathlib import Path

SRC = Path(__file__).resolve().parent
sys.path.insert(0, str(SRC))

from fastapi import APIRouter, Depends, FastAPI, HTTPException, Request  # noqa: E402
from fastapi.responses import JSONResponse  # noqa: E402
from fastapi.security import APIKeyHeader  # noqa: E402
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator  # noqa: E402

import detect as detect_mod  # noqa: E402
import detect_rules as dr  # noqa: E402
import ner_detect  # noqa: E402
from common import DECISION_MODEL, DICT_DIR, KEEP_ALIVE, LLM_MODEL, OLLAMA, post_json, utf8_stdout  # noqa: E402
from decide import decide  # noqa: E402
from detect import detect  # noqa: E402
from mask import PLACEHOLDER_RE, TIER, instruction_for_external, mask, restore  # noqa: E402
from route import DEFAULT_VARIANT, VARIANTS, route  # noqa: E402
import anthropic  # noqa: E402
from answer_external import MODEL as EXTERNAL_MODEL, answer_external, has_key, leak_check, run_external  # noqa: E402

SERVICE = "woowang-model-service"
VERSION = "0.1.0"
EMBED_MODEL = "bge-m3-cpu"
MAX_CHARS = 60_000           # extract.MAX_CHARS 와 같다. 넘으면 백엔드가 나눠서 보낸다
BODY_SEP = "\n\n"            # instruction + body 를 한 글로 합칠 때 사이. accept_run.py 와 같다
LOCAL_SYSTEM = ("너는 회사 내부 업무 도우미다. 사용자의 요청을 한국어로 처리한다. "
                "문서에 없는 사실은 추가하지 않고, 요청하지 않은 설명은 덧붙이지 않는다.")
LOCAL_CTX_WARN_CHARS = 6000  # num_ctx 4096 고정(바꾸면 30B 재로드). 1.7자/토큰이면 이 길이부터 입력이 잘릴 수 있다

log = logging.getLogger("server")
LLM_LOCK = threading.Lock()
STATE = {"started": time.time(), "requests": 0, "errors": 0, "analyze": 0, "ner_ready": False, "warm": {}, "dict_hash": ""}


# ---------- 버전·해시 ----------

def _hash_files(paths) -> str:
    h = hashlib.sha1()
    for p in paths:
        if p.exists():
            h.update(p.name.encode()); h.update(p.read_bytes())
    return h.hexdigest()[:10]


CODE_HASH = _hash_files(SRC / n for n in ("detect_rules.py", "detect.py", "detect_llm.py", "decide.py", "mask.py", "route.py", "ner_detect.py"))


def dict_hash() -> str:
    return _hash_files(DICT_DIR / name for name, _, _ in dr.DICTS)


def versions() -> dict:
    return {"service": SERVICE, "version": VERSION, "code": CODE_HASH, "dict": STATE["dict_hash"],
            "llm_model": LLM_MODEL, "prompt_mode": detect_mod.PROMPT_MODE, "route_model": DECISION_MODEL,
            "route_variant": DEFAULT_VARIANT, "ner_model": ner_detect.DEFAULT_MODEL, "embed_model": EMBED_MODEL}


# ---------- 인증 ----------

def _load_keys() -> list[str]:
    keys = [k.strip() for k in os.environ.get("MODEL_API_KEYS", "").split(",") if k.strip()]
    if not keys:
        k = secrets.token_urlsafe(24)
        print(f"[server] MODEL_API_KEYS 가 비어 있어 임시 키를 만들었다 (이번 실행에만 유효): {k}", file=sys.stderr, flush=True)
        keys = [k]
    return keys


KEYS = _load_keys()
api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)


def require_key(key: str | None = Depends(api_key_header)) -> None:
    if key and any(hmac.compare_digest(key, k) for k in KEYS):
        return
    raise HTTPException(status_code=401, detail="X-API-Key 헤더가 없거나 틀림")


# ---------- 입력 형식 ----------

class Policy(BaseModel):
    model_config = ConfigDict(extra="ignore")
    mask_person: bool = False
    mask_company: bool = True


class TextIn(BaseModel):
    """text 하나로 보내거나, instruction(요청문) + body(문서 본문)로 보낸다. 둘로 보내면 서버가 '요청문\\n\\n본문'으로 합치고
    body_offset(본문이 시작하는 글자 번호)을 돌려준다. 구간 위치는 합친 글 기준이니 본문 하이라이트는 start - body_offset."""
    model_config = ConfigDict(extra="ignore")
    text: str | None = Field(default=None, max_length=MAX_CHARS)
    instruction: str | None = Field(default=None, max_length=4000)
    body: str | None = Field(default=None, max_length=MAX_CHARS)
    request_id: str | None = Field(default=None, max_length=64)
    doc_name: str | None = Field(default=None, max_length=255)

    @model_validator(mode="after")
    def _one_of(self):
        if (self.text is None) == (self.body is None):
            raise ValueError("text 또는 body 중 하나를 보낸다")
        if not (self.text if self.text is not None else self.body).strip():
            raise ValueError("빈 글")
        return self

    def composed(self) -> tuple[str, int]:
        if self.text is not None:
            return self.text, 0
        instr = (self.instruction or "").strip()
        if instr:
            return instr + BODY_SEP + self.body, len(instr) + len(BODY_SEP)
        return self.body, 0


class AnalyzeIn(TextIn):
    policy: Policy = Policy()
    use_llm: bool = True                   # False면 즉시 경로만 (간단 모드 재현·테스트용)
    route_variant: str = DEFAULT_VARIANT

    @field_validator("route_variant")
    @classmethod
    def _known_variant(cls, v):
        if v not in VARIANTS:
            raise ValueError(f"route_variant 는 {sorted(VARIANTS)} 중 하나")
        return v


class SpanIn(BaseModel):
    model_config = ConfigDict(extra="ignore")
    start: int = Field(ge=0)
    end: int = Field(ge=0)
    text: str = ""
    label: str
    sources: list[str] = []


class MaskIn(BaseModel):
    model_config = ConfigDict(extra="ignore")
    text: str = Field(max_length=MAX_CHARS)
    spans: list[SpanIn]
    policy: Policy = Policy()


class RestoreIn(BaseModel):
    model_config = ConfigDict(extra="ignore")
    answer: str = Field(max_length=400_000)
    mapping: dict[str, str]


class AnswerLocalIn(TextIn):
    max_tokens: int = Field(default=1024, ge=16, le=4096)


class AnswerExternalIn(BaseModel):
    """두 가지 중 하나. (a) masked + mapping: /analyze 가 돌려준 가림 본문과 대응표를 그대로 보낸다(승인 뒤 전송).
    (b) text + spans (+ policy): 서버가 가림부터 한다. 둘 다 보내기 직전에 원문 값이 남았는지 검사한다."""
    model_config = ConfigDict(extra="ignore")
    masked: str | None = Field(default=None, max_length=MAX_CHARS + 4000)
    mapping: dict[str, str] | None = None
    text: str | None = Field(default=None, max_length=MAX_CHARS + 4000)
    spans: list[SpanIn] | None = None
    policy: Policy = Policy()
    request_id: str | None = Field(default=None, max_length=64)
    model: str = EXTERNAL_MODEL
    effort: str = Field(default="medium", pattern="^(low|medium|high|xhigh|max)$")
    max_tokens: int = Field(default=16000, ge=256, le=32000)
    fallback: bool = True

    @model_validator(mode="after")
    def _one_of(self):
        a = self.masked is not None or self.mapping is not None
        b = self.text is not None or self.spans is not None
        if a == b:
            raise ValueError("masked+mapping 또는 text+spans 중 한 쌍만 보낸다")
        if a and (self.masked is None or self.mapping is None):
            raise ValueError("masked 와 mapping 을 함께 보낸다")
        if b and (self.text is None or self.spans is None):
            raise ValueError("text 와 spans 를 함께 보낸다")
        if a and not self.masked.strip():
            raise ValueError("빈 가림 본문")
        return self


class EmbedIn(BaseModel):
    model_config = ConfigDict(extra="ignore")
    texts: list[str] = Field(min_length=1, max_length=64)


class DictReloadIn(BaseModel):
    """목록을 주면 사전 파일을 그 내용으로 바꾼 뒤 재적재, 비우면 파일만 다시 읽는다. 한 항목에 '|'로 별칭을 나란히 적을 수 있다."""
    model_config = ConfigDict(extra="ignore")
    companies: list[str] | None = None
    projects: list[str] | None = None


# ---------- 도우미 ----------

def span_out(sp) -> dict:
    d = sp.to_dict() if hasattr(sp, "to_dict") else dict(sp)
    d["tier"] = TIER.get(d["label"], 3)
    return d


def ollama_get(path: str, timeout: float = 3.0) -> dict:
    with urllib.request.urlopen(OLLAMA + path, timeout=timeout) as r:
        return json.loads(r.read().decode("utf-8"))


def detect_locked(text: str):
    """30B 호출이 든 탐지. GPU 하나라 한 번에 하나만."""
    with LLM_LOCK:
        return detect(text)


def llm_failed(det: dict) -> bool:
    return any(w.startswith("정밀 검사(30B) 호출 실패") for w in det.get("warnings", []))


def reload_dicts() -> dict:
    dr.DICTS[:] = [(name, label, [(t, dr.term_regex(t)) for t in dr.load_dict(name)]) for name, label, _ in dr.DICTS]
    STATE["dict_hash"] = dict_hash()
    return {name: len(terms) for name, _, terms in dr.DICTS}


def write_dict(name: str, lines: list[str]) -> None:
    """사전 파일 교체. 이전 파일은 .bak 으로 남긴다."""
    path = DICT_DIR / name
    clean = [ln.strip() for ln in lines if ln and ln.strip()]
    if path.exists():
        shutil.copy2(path, path.with_suffix(".bak"))
    tmp = path.with_suffix(".tmp")
    tmp.write_text("\n".join(clean) + ("\n" if clean else ""), encoding="utf-8")
    os.replace(tmp, path)


def answer_local_sync(text: str, max_tokens: int) -> dict:
    body = {
        "model": LLM_MODEL,
        "messages": [{"role": "system", "content": LOCAL_SYSTEM}, {"role": "user", "content": text}],
        "stream": False, "keep_alive": KEEP_ALIVE,
        # num_ctx 는 탐지와 같은 4096 (다르면 30B 재로드 14~17초). num_predict·temperature 는 재로드 없이 바뀐다
        "options": {"temperature": 0, "num_ctx": 4096, "num_predict": max_tokens},
    }
    with LLM_LOCK:
        resp, secs = post_json("/api/chat", body, timeout=240)
    return {
        "answer": resp.get("message", {}).get("content", ""), "model": LLM_MODEL, "seconds": round(secs, 3),
        "prompt_tokens": resp.get("prompt_eval_count"), "eval_tokens": resp.get("eval_count"),
        "done_reason": resp.get("done_reason"), "truncated": resp.get("done_reason") == "length",
    }


def warm_ollama() -> None:
    """시작 뒤 배경에서 세 모델을 한 번씩 불러 상주시킨다 (30B 첫 로드 14~17초). 실패해도 서비스는 뜬다."""
    sample = "예열용 짧은 문장입니다. 담당 김지영 과장(010-0000-0000)에게 연락 바랍니다."
    for name, fn in (("route", lambda: route(sample)), ("llm", lambda: detect_locked(sample)),
                     ("embed", lambda: post_json("/api/embed", {"model": EMBED_MODEL, "input": sample, "keep_alive": KEEP_ALIVE}, timeout=300))):
        t0 = time.perf_counter()
        try:
            fn()
            STATE["warm"][name] = round(time.perf_counter() - t0, 1)
        except Exception as e:  # Ollama 가 꺼져 있어도 서비스는 떠 있어야 한다
            STATE["warm"][name] = f"실패: {str(e)[:120]}"
    log.info("예열 끝: %s", STATE["warm"])


# ---------- 앱 ----------

@asynccontextmanager
async def lifespan(app: FastAPI):
    t0 = time.perf_counter()
    STATE["dict_hash"] = dict_hash()
    try:
        r = detect("예열입니다. 담당 김지영 과장.", use_llm=False)  # NER 모델 로딩 8~14초
        STATE["ner_ready"] = "ner_error" not in r["timing"]
    except Exception as e:
        log.warning("NER 예열 실패: %s", e)
    log.info("시작 %.1fs · NER %s · 사전 %s · 키 %d개", time.perf_counter() - t0, STATE["ner_ready"],
             {n: len(t) for n, _, t in dr.DICTS}, len(KEYS))
    if os.environ.get("MODEL_WARM_OLLAMA", "1") != "0":
        threading.Thread(target=warm_ollama, daemon=True).start()
    yield


app = FastAPI(title="AI 교환기 모델 서비스", version=VERSION, lifespan=lifespan)
protected = APIRouter(dependencies=[Depends(require_key)])


@app.middleware("http")
async def access_log(request: Request, call_next):
    t0 = time.perf_counter()
    response = await call_next(request)
    STATE["requests"] += 1
    if response.status_code >= 500:
        STATE["errors"] += 1
    log.info("%s %s %d %.0fms", request.method, request.url.path, response.status_code, (time.perf_counter() - t0) * 1000)
    return response


@app.exception_handler(Exception)
async def unhandled(request: Request, exc: Exception):
    STATE["errors"] += 1
    log.exception("처리 실패 %s %s", request.method, request.url.path)
    return JSONResponse(status_code=500, content={"error": type(exc).__name__, "detail": str(exc)[:300]})


@app.get("/health")
async def health():
    return {"ok": True, "service": SERVICE, "version": VERSION}


@protected.get("/status")
async def status():
    try:
        ps = ollama_get("/api/ps")
        models = [{"name": m.get("name"), "size_gb": round(m.get("size", 0) / 1e9, 1), "vram_gb": round(m.get("size_vram", 0) / 1e9, 1)}
                  for m in ps.get("models", [])]
        ollama = {"ok": True, "loaded": models}
    except Exception as e:
        ollama = {"ok": False, "error": str(e)[:200]}
    return {"ok": True, "uptime_s": round(time.time() - STATE["started"]), "requests": STATE["requests"], "errors": STATE["errors"],
            "analyze": STATE["analyze"], "ner_ready": STATE["ner_ready"], "warm": STATE["warm"], "ollama": ollama,
            "dict": {name: len(terms) for name, _, terms in dr.DICTS}, "llm_busy": LLM_LOCK.locked(),
            "external": {"key": has_key(), "model": EXTERNAL_MODEL}, "versions": versions()}


@protected.post("/detect/instant")
async def detect_instant(inp: TextIn):
    text, off = inp.composed()
    t0 = time.perf_counter()
    r = await asyncio.to_thread(detect, text, use_llm=False)
    return {"request_id": inp.request_id, "doc_name": inp.doc_name, "text_chars": len(text), "body_offset": off,
            "spans": [span_out(s) for s in r["spans"]], "sensitive": r["sensitive"],
            "timing": {**r["timing"], "total_ms": round((time.perf_counter() - t0) * 1000, 1)},
            "warnings": r["warnings"], "versions": versions()}


@protected.post("/analyze")
async def analyze(inp: AnalyzeIn):
    """탐지(규칙·NER·30B)와 라우팅(tev1)을 동시에 돌리고 결정 규칙과 가림을 적용한다. 30B·tev1 이 죽어 있어도 200으로 답하고
    mode 를 degraded 로 표시한다 (30B 실패 → 즉시 경로 결과만, tev1 실패 → 사내 처리 폴백)."""
    text, off = inp.composed()
    t0 = time.perf_counter()

    async def run_detect():
        if inp.use_llm:
            return await asyncio.to_thread(detect_locked, text)
        return await asyncio.to_thread(detect, text, use_llm=False)

    async def run_route():
        try:
            return await asyncio.to_thread(route, text, inp.route_variant), None
        except Exception as e:
            return None, f"{type(e).__name__}: {str(e)[:200]}"

    det, (rt, rt_err) = await asyncio.gather(run_detect(), run_route())
    d = decide(text, det["spans"], rt)
    m = mask(text, det["spans"], inp.policy.model_dump())
    warnings = list(det["warnings"]) + list(d["warnings"])
    if rt_err:
        warnings.append(f"라우팅(tev1) 호출 실패 → 사내 처리 폴백: {rt_err}")
    if not inp.use_llm:
        mode = "instant_only"
    elif llm_failed(det) or rt_err:
        mode = "degraded"
    else:
        mode = "full"
    total = round(time.perf_counter() - t0, 3)
    STATE["analyze"] += 1
    log.info("analyze id=%s chars=%d spans=%d action=%s approval=%s mode=%s %.2fs",
             inp.request_id, len(text), len(det["spans"]), d["action"], d["needs_approval"], mode, total)
    placeholder_at = {(e["start"], e["end"]): e["placeholder"] for e in m["entries"]}  # 화면 하이라이트용: 구간마다 가려졌는지와 자리표
    return {
        "request_id": inp.request_id, "doc_name": inp.doc_name, "text_chars": len(text), "body_offset": off, "mode": mode,
        "spans": [{**span_out(s), "masked": (s.start, s.end) in placeholder_at, "placeholder": placeholder_at.get((s.start, s.end))}
                  for s in det["spans"]],
        "rule_spans": [span_out(s) for s in det["rule_spans"]],
        "llm_spans": [span_out(s) for s in det["llm_spans"]],
        "sensitive": det["sensitive"],
        "route": rt, "route_error": rt_err,
        "decision": {k: d[k] for k in ("action", "needs_approval", "reasons", "warnings")},
        "mask": m,
        "external_instruction": instruction_for_external(),
        "warnings": warnings, "dropped": det["dropped"],
        "timing": {**det["timing"], "route_s": rt["seconds"] if rt else None, "total_s": total},
        "versions": versions(),
    }


@protected.post("/mask")
async def mask_endpoint(inp: MaskIn):
    n = len(inp.text)
    for s in inp.spans:
        if s.end <= s.start or s.end > n:
            raise HTTPException(status_code=422, detail=f"구간 위치가 글 밖: {s.start}-{s.end} (글 {n}자)")
    return mask(inp.text, [s.model_dump() for s in inp.spans], inp.policy.model_dump())


@protected.post("/restore")
async def restore_endpoint(inp: RestoreIn):
    restored = restore(inp.answer, inp.mapping)
    left = sorted({m.group(0) for m in PLACEHOLDER_RE.finditer(restored)})  # 대응표에 없어 그대로 둔 자리표 (추측해 채우지 않는다)
    return {"restored": restored, "unresolved": left}


@protected.post("/answer_local")
async def answer_local(inp: AnswerLocalIn):
    text, _ = inp.composed()
    warnings = []
    if len(text) > LOCAL_CTX_WARN_CHARS:
        warnings.append(f"글이 {len(text):,}자: 문맥 4,096토큰을 넘으면 앞부분이 잘릴 수 있음")
    try:
        r = await asyncio.to_thread(answer_local_sync, text, inp.max_tokens)
    except (RuntimeError, OSError) as e:
        raise HTTPException(status_code=503, detail=f"30B 호출 실패: {str(e)[:200]}")
    log.info("answer_local id=%s chars=%d out_tokens=%s %.1fs", inp.request_id, len(text), r["eval_tokens"], r["seconds"])
    return {"request_id": inp.request_id, **r, "warnings": warnings}


@protected.post("/answer_external")
async def answer_external_endpoint(inp: AnswerExternalIn):
    """외부 LLM 호출(4.2). 가림 본문만 나간다. 응답의 answer 는 자리표 그대로, restored 는 원문으로 되돌린 것."""
    if not has_key():
        raise HTTPException(status_code=503, detail="외부 LLM 키 미설정 (환경변수 ANTHROPIC_API_KEY)")
    kw = dict(model=inp.model, effort=inp.effort, max_tokens=inp.max_tokens, fallback=inp.fallback)
    try:
        if inp.masked is not None:
            leaks = leak_check(inp.masked, inp.mapping)
            if leaks:
                raise HTTPException(status_code=409, detail=f"전송 중단: 가림 본문에 원문 값 {len(leaks)}개 남음")
            r = await asyncio.to_thread(answer_external, inp.masked, inp.mapping, **kw)
        else:
            r = await asyncio.to_thread(run_external, inp.text, [s.model_dump() for s in inp.spans], inp.policy.model_dump(), **kw)
    except ValueError as e:  # run_external 의 유출 검사
        raise HTTPException(status_code=409, detail=str(e)[:300])
    except anthropic.AuthenticationError:
        raise HTTPException(status_code=503, detail="외부 LLM 키가 틀리거나 만료됨 (401)")
    except anthropic.RateLimitError as e:
        raise HTTPException(status_code=429, detail=f"외부 LLM 호출 한도: {str(e)[:200]}")
    except anthropic.APIStatusError as e:
        raise HTTPException(status_code=502, detail=f"외부 LLM 오류 {e.status_code}: {str(e)[:200]}")
    except anthropic.APIConnectionError as e:
        raise HTTPException(status_code=502, detail=f"외부 LLM 연결 실패: {str(e)[:200]}")
    log.info("answer_external id=%s in=%s out=%s stop=%s cost=%s %.1fs", inp.request_id, r["usage"]["input_tokens"],
             r["usage"]["output_tokens"], r["stop_reason"], r["cost_usd"], r["seconds"])
    return {"request_id": inp.request_id, **r}


@protected.post("/embed")
async def embed(inp: EmbedIn):
    try:
        resp, secs = await asyncio.to_thread(post_json, "/api/embed", {"model": EMBED_MODEL, "input": inp.texts, "keep_alive": KEEP_ALIVE}, 300)
    except (RuntimeError, OSError) as e:
        raise HTTPException(status_code=503, detail=f"임베딩 호출 실패: {str(e)[:200]}")
    vecs = resp.get("embeddings", [])
    return {"model": EMBED_MODEL, "dim": len(vecs[0]) if vecs else 0, "embeddings": vecs, "seconds": round(secs, 3)}


@protected.post("/dict/reload")
async def dict_reload(inp: DictReloadIn):
    written = []
    if inp.companies is not None:
        write_dict("companies.txt", inp.companies); written.append("companies.txt")
    if inp.projects is not None:
        write_dict("projects.txt", inp.projects); written.append("projects.txt")
    counts = reload_dicts()
    log.info("dict reload written=%s counts=%s", written, counts)
    return {"ok": True, "written": written, "terms": counts, "dict_hash": STATE["dict_hash"]}


app.include_router(protected)


if __name__ == "__main__":
    utf8_stdout()
    ap = argparse.ArgumentParser(description="AI 교환기 모델 서비스")
    ap.add_argument("--host", default="127.0.0.1", help="Tailscale 로 열 때는 0.0.0.0 또는 테일스케일 IP")
    ap.add_argument("--port", type=int, default=8010)
    ap.add_argument("--log-level", default="info")
    a = ap.parse_args()
    import uvicorn
    uvicorn.run(app, host=a.host, port=a.port, log_level=a.log_level)
