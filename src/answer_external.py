"""외부 LLM 호출과 복원 (흐름도 ⑤, 4.2 외부). 가림 본문을 Anthropic API로 보내고 답변의 자리표를 원문으로 되돌린다.

answer_external(masked, mapping, model=MODEL, effort=EFFORT, max_tokens=MAX_TOKENS, fallback=True) -> dict
run_external(text, spans, policy=None, **kw) -> dict   # mask → leak_check → answer_external → restore 한 번에
leak_check(masked, mapping) -> [str]                     # 전송 직전 안전장치: 원문 값이 가림 본문에 남아 있으면 그 값들. 0건이어야 보낸다

키:   환경변수 ANTHROPIC_API_KEY (SDK가 읽는다). 코드·로그·git·Notion에 적지 않는다.
모델: 기본 claude-sonnet-5-5 (팀 요구사항 분석서의 선택, $2/$10 per MTok). 환경변수 EXTERNAL_MODEL 로 바꾼다.
생각: 5.5 계열은 적응형 생각이 기본으로 켜져 있고 깊이는 output_config.effort 로 조절한다. 번역·요약이라 기본 medium.
거부: stop_reason == "refusal" 이면 answer 는 빈 문자열이고 refusal 에 category·explanation 이 담긴다. fallback=True 면 서버 쪽
      대체 모델(fallbacks="default", 베타)이 같은 호출 안에서 이어받는다. 대체 모델도 Anthropic 모델이라 가림 본문만 받는 점은 같다.
반환: answer(자리표 그대로), restored(복원), unresolved(대응표에 없는 자리표), placeholders{sent, kept}, stop_reason, truncated,
      refusal, model, served_by, fallback_ran, usage{input_tokens, output_tokens, cache_read, cache_write}, cost_usd(추정), seconds, anthropic_request_id
"""
import os
import sys
import time

import anthropic

from mask import PLACEHOLDER_RE, instruction_for_external, mask, restore

MODEL = os.environ.get("EXTERNAL_MODEL", "claude-sonnet-5-5")
EFFORT = os.environ.get("EXTERNAL_EFFORT", "medium")   # low | medium | high | xhigh | max
MAX_TOKENS = 16000
TIMEOUT_S = 180
FALLBACK_BETA = "server-side-fallback-2026-07-01"
# USD / 1M 토큰 (입력, 출력, 캐시 읽기). 2026-10 가격표 기준 추정용. 실제 청구는 Console 에서 본다
PRICES = {"claude-sonnet-5-5": (2.0, 10.0, 0.20), "claude-opus-5-5": (4.0, 20.0, 0.20), "claude-haiku-5-5": (0.10, 0.50, 0.01)}

_client = None


def has_key() -> bool:
    return bool(os.environ.get("ANTHROPIC_API_KEY") or os.environ.get("ANTHROPIC_AUTH_TOKEN"))


def client() -> anthropic.Anthropic:
    global _client
    if _client is None:
        _client = anthropic.Anthropic(timeout=TIMEOUT_S, max_retries=2)
    return _client


def leak_check(masked: str, mapping: dict) -> list[str]:
    """가림 본문에 원문 값이 글자 그대로 남아 있으면 돌려준다 (분석서 ⑤ 완료 조건: 전송 직전 본문에 정답 구간 문자열 0건)."""
    return [v for v in mapping.values() if v and v in masked]


def _tags(text: str) -> set:
    return {(m.group(1).upper(), m.group(2)) for m in PLACEHOLDER_RE.finditer(text)}


def estimate_cost(model: str, usage: dict) -> float | None:
    p = PRICES.get(model)
    if not p:
        return None
    return round((usage["input_tokens"] * p[0] + usage["output_tokens"] * p[1] + usage["cache_read"] * p[2]) / 1e6, 5)


def answer_external(masked: str, mapping: dict, model: str = MODEL, effort: str = EFFORT, max_tokens: int = MAX_TOKENS,
                    fallback: bool = True) -> dict:
    """가림 본문 하나를 보내고 답변을 복원한다. anthropic 예외(AuthenticationError, RateLimitError, APIConnectionError …)는 그대로 올린다."""
    kwargs = dict(model=model, max_tokens=max_tokens, system=instruction_for_external(),
                  messages=[{"role": "user", "content": masked}], output_config={"effort": effort})
    notes = []
    t0 = time.perf_counter()
    if fallback:
        try:
            resp = client().beta.messages.create(betas=[FALLBACK_BETA], fallbacks="default", **kwargs)
        except TypeError as e:  # 설치된 SDK 가 fallbacks 인자를 모름
            notes.append(f"fallback 미적용(SDK): {str(e)[:100]}")
            resp = client().messages.create(**kwargs)
        except anthropic.BadRequestError as e:
            if "fallback" not in str(e).lower():
                raise
            notes.append(f"fallback 미적용(API): {str(e)[:100]}")
            resp = client().messages.create(**kwargs)
    else:
        resp = client().messages.create(**kwargs)
    secs = time.perf_counter() - t0

    text = "".join(b.text for b in resp.content if b.type == "text")
    refusal = None
    if resp.stop_reason == "refusal":
        sd = getattr(resp, "stop_details", None)
        refusal = {"category": getattr(sd, "category", None), "explanation": getattr(sd, "explanation", None)}
    iters = getattr(resp.usage, "iterations", None) or []
    fallback_ran = any(getattr(it, "type", None) == "fallback_message" for it in iters)
    restored = restore(text, mapping) if text else ""
    sent, kept = _tags(masked), _tags(text) & _tags(masked)
    usage = {"input_tokens": resp.usage.input_tokens, "output_tokens": resp.usage.output_tokens,
             "cache_read": getattr(resp.usage, "cache_read_input_tokens", 0) or 0,
             "cache_write": getattr(resp.usage, "cache_creation_input_tokens", 0) or 0}
    served_by = getattr(resp, "model", None) or model
    return {
        "answer": text, "restored": restored,
        "unresolved": sorted({m.group(0) for m in PLACEHOLDER_RE.finditer(restored)}),
        "placeholders": {"sent": len(sent), "kept": len(kept)},
        "stop_reason": resp.stop_reason, "truncated": resp.stop_reason == "max_tokens", "refusal": refusal,
        "model": model, "served_by": served_by, "fallback_ran": fallback_ran, "effort": effort,
        "usage": usage, "cost_usd": estimate_cost(served_by, usage), "seconds": round(secs, 3),
        "anthropic_request_id": getattr(resp, "_request_id", None), "notes": notes,  # 장애 문의용. 서버 응답의 request_id 는 백엔드 것
    }


def run_external(text: str, spans, policy: dict | None = None, **kw) -> dict:
    """탐지 구간을 받아 가림 → 유출 검사 → 외부 호출 → 복원. 가림 본문에 원문 값이 남아 있으면 보내지 않고 ValueError."""
    m = mask(text, spans, policy)
    leaks = leak_check(m["masked"], m["mapping"])
    if leaks:
        raise ValueError(f"전송 중단: 가림 본문에 원문 값 {len(leaks)}개 남음: {leaks[:3]}")
    r = answer_external(m["masked"], m["mapping"], **kw)
    r.update({"masked": m["masked"], "mapping": m["mapping"], "entries": m["entries"], "unmasked": m["unmasked"], "policy": m["policy"]})
    return r


if __name__ == "__main__":
    from common import utf8_stdout
    utf8_stdout()
    if not has_key():
        sys.exit("ANTHROPIC_API_KEY 가 없다. PowerShell 에서 setx ANTHROPIC_API_KEY \"<키>\" 로 등록한 뒤 새 창에서 실행.")
    r = answer_external("[[ORG_1]] 담당자에게 보낼 인사 한 문장을 써 주세요. 자리표는 그대로 두세요.", {"[[ORG_1]]": "한빛에어로"})
    print({k: v for k, v in r.items() if k not in ("answer",)})
