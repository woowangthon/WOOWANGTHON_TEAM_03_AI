"""30B 구간 추출기: Ollama /api/chat + JSON 스키마 강제 + 원문 포함 검사.

- 지시는 한국어 (영어 시스템 프롬프트는 10-28 실측에서 0건 추출)
- label은 스키마 enum으로 강제 (없으면 날짜 등 오탐)
- 돌려준 text가 원문에 그대로 없으면 버리고 dropped에 기록 (환각 방지)
- 생성 토큰 상한(num_predict)과 호출 시간 제한을 둔다. 10-29 B04-3(값 목록이 두 번 반복되는 글)에서 30B가 같은 구간을
  23,000토큰 넘게 반복 생성해 Ollama 10분 제한에 걸린 뒤 500으로 죽은 일이 있었다. 상한에서 끊기면 완성된 객체만 건져 쓴다.
"""
import json
import re
import sys
import time

from common import LABELS, LLM_MODEL, KEEP_ALIVE, Span, post_json, find_all, utf8_stdout

MAX_PREDICT = 768   # 구간 하나가 15~20토큰이니 40개 넘게 담긴다. 반복 생성 폭주를 20초 안에서 끊는 용도.
TIMEOUT_S = 90      # 모델 재로드(14~17s) + 긴 글 prompt_eval(3s) + 상한 생성(20s)보다 넉넉하게
_OBJ_RE = re.compile(r"\{[^{}]*\}")  # 끊긴 JSON에서 완성된 객체 조각. 키 순서는 모델이 {"label":…,"text":…}로도 내므로 json.loads로 해석(밤 배치 3 영어 E01-4)

SYSTEM_PROMPT = """너는 방산 협력 제조 회사의 정보 유출 방지(DLP) 검사기다.
아래 텍스트를 외부 AI 서비스로 보내기 전에 가려야 할 민감 구간을 모두 찾아라.

가릴 대상과 label:
- company: 고객사, 협력사, 거래처 등 회사 이름
- project: 사업명, 프로젝트명, 무기체계명
- doc_no: 도면번호, 품번, 발주번호, 로트번호, 계약번호 같은 내부 식별 번호
- price: 단가, 금액, 견적가, 지체상금 등 돈
- person: 사람 이름
- contact: 전화번호, 이메일, 주소
- biz_no: 사업자등록번호, 주민등록번호

규칙:
1. text는 원문에 나온 글자 그대로 복사한다(정확한 부분 문자열). 바꾸거나 줄이거나 번역하지 않는다.
2. 공개 규격·표준 번호(MIL-, AWS, ASTM, ISO, KS 등)와 재질 기호(6061-T6 등)는 가리지 않는다.
3. 치수, 하중, 경도, 수량, 날짜, 통계 수치는 가리지 않는다.
4. 민감 구간이 없으면 spans를 빈 배열로 돌려준다.
JSON만 출력한다: {"spans":[{"text":"...","label":"..."}]}"""

SCHEMA = {
    "type": "object",
    "properties": {
        "spans": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "text": {"type": "string"},
                    "label": {"type": "string", "enum": LABELS},
                },
                "required": ["text", "label"],
            },
        }
    },
    "required": ["spans"],
}


def _parse_items(content: str, meta: dict):
    """JSON 전체 파싱. 상한에서 끊겨 깨진 JSON이면 완성된 {"text","label"} 객체만 건진다."""
    try:
        parsed = json.loads(content)
        return parsed.get("spans", []) if isinstance(parsed, dict) else []
    except json.JSONDecodeError:
        pass
    items = []
    for m in _OBJ_RE.finditer(content):
        try:
            obj = json.loads(m.group(0))
        except json.JSONDecodeError:
            continue
        if isinstance(obj, dict) and obj.get("text") and obj.get("label"):
            items.append({"text": obj["text"], "label": obj["label"]})
    meta["dropped"].append({"text": content[:200], "reason": "json_parse_error", "salvaged": len(items)})
    return items


def detect_llm(text: str, model: str = LLM_MODEL, num_ctx: int = 4096, system_prompt: str = SYSTEM_PROMPT,
               num_predict: int = MAX_PREDICT, timeout: float = TIMEOUT_S, labels: list | None = None):
    """(spans, meta) 반환. meta에 지연과 토큰 수, 버린 구간, truncated/error. system_prompt를 바꾸면 few-shot 실험 등에 쓸 수 있다.
    labels를 주면 스키마 enum을 그 라벨로 제한한다(예: 규칙이 못 찾는 company/project/person만 30B에 맡기는 실험).
    호출 실패(시간 초과, 5xx, 연결 불가)면 예외 대신 빈 spans와 meta["error"]를 돌려준다 → 호출 쪽은 규칙 결과만으로 진행."""
    schema = SCHEMA
    if labels:
        schema = json.loads(json.dumps(SCHEMA))
        schema["properties"]["spans"]["items"]["properties"]["label"]["enum"] = list(labels)
    body = {
        "model": model,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": text},
        ],
        "format": schema,
        "stream": False,
        "keep_alive": KEEP_ALIVE,
        "options": {"temperature": 0, "num_ctx": num_ctx, "num_predict": num_predict},
    }
    try:
        resp, total_s = post_json("/api/chat", body, timeout=timeout)
    except (RuntimeError, OSError) as e:  # HTTP 5xx(RuntimeError), 시간 초과·연결 실패(OSError 계열)
        print(f"[detect_llm] 30B 호출 실패 → 규칙 결과만 사용: {str(e)[:200]}", file=sys.stderr)
        return [], {"model": model, "total_s": None, "error": str(e)[:300], "truncated": False, "dropped": [], "raw": ""}
    content = resp.get("message", {}).get("content", "")
    meta = {
        "model": model,
        "total_s": round(total_s, 3),
        "load_s": round(resp.get("load_duration", 0) / 1e9, 3),
        "prompt_eval_s": round(resp.get("prompt_eval_duration", 0) / 1e9, 3),
        "eval_s": round(resp.get("eval_duration", 0) / 1e9, 3),
        "prompt_tokens": resp.get("prompt_eval_count"),
        "eval_tokens": resp.get("eval_count"),
        "done_reason": resp.get("done_reason"),
        "truncated": resp.get("done_reason") == "length",
        "dropped": [],
        "raw": content,
    }
    items = _parse_items(content, meta)
    if not items:
        return [], meta

    spans = []
    seen = set()
    for it in items:
        t = str(it.get("text", "")).strip()
        label = it.get("label", "other")
        if label not in LABELS:
            label = "other"
        if not t:
            continue
        hits = find_all(text, t)
        if not hits:
            # 끝의 구두점만 다른 경우 한 번 더 시도
            t2 = t.rstrip(".,)]」』\"'")
            hits = find_all(text, t2) if t2 and t2 != t else []
            if hits:
                t = t2
        if not hits:
            meta["dropped"].append({"text": t, "label": label, "reason": "not_in_input"})
            continue
        for s, e in hits:
            if (s, e) in seen:
                continue
            seen.add((s, e))
            spans.append(Span(s, e, text[s:e], label, ["llm"]))
    spans.sort(key=lambda s: (s.start, -s.end))
    return spans, meta


if __name__ == "__main__":
    utf8_stdout()
    sample = sys.stdin.read() if not sys.stdin.isatty() else (
        "고객사 LIG넥스원 도면 DWG-2025-0417, 단가 850,000원, 담당은 박지훈 대리(010-2345-6789)")
    spans, meta = detect_llm(sample)
    for sp in spans:
        print(f"[{sp.label}] {sp.text}")
    print({k: v for k, v in meta.items() if k != "raw"})
