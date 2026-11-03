"""가림·복원: 탐지 구간을 자리표로 바꾸고(외부 전송용), 외부 응답의 자리표를 원문으로 되돌린다. (흐름도 A 5~6번)

mask(text, spans, policy) -> {
  "masked": str,                 # 외부 모델에 보낼 본문
  "mapping": {"[[ORG_1]]": "(주)한빛에어로", ...},
  "entries": [{start, end, text, label, placeholder}],   # 카드 하이라이트와 로그용
  "unmasked": [{start, end, text, label, reason}],       # 정책으로 가리지 않은 구간(등급 2·3)
  "policy": {...},
}
restore(answer, mapping) -> str   # 자리표의 변형(공백, 괄호 하나, 소문자, _↔-)도 되돌린다
instruction_for_external() -> str  # 외부 요청 앞에 붙이는 한 줄

설계(10-29 시연 문서 세트 v1):
- 자리표는 언어 중립 [[ORG_1]] 형태. 번역 요청에서 한국어 라벨은 번역돼 사라질 수 있다.
- 같은 라벨·같은 표기는 같은 번호. 외부 모델이 "ORG_1이 두 번 나온다"는 문맥을 유지한다.
- 등급 1(식별번호·금액·연락처·사업자번호·사업명·회사명)은 항상 가림. 등급 2(사람)는 policy["mask_person"]일 때만.
  회사명은 policy["mask_company"]=False로 내릴 수 있다. 등급 3(날짜·수량·치수)은 탐지 라벨에 없다.
"""
import re

from common import Span

PLACEHOLDER = {"company": "ORG", "project": "PROJECT", "doc_no": "ID", "price": "AMT", "contact": "CONTACT",
               "biz_no": "BIZNO", "person": "PERSON", "other": "X"}
TIER = {"doc_no": 1, "price": 1, "contact": 1, "biz_no": 1, "project": 1, "company": 1, "person": 2, "other": 3}
DEFAULT_POLICY = {"mask_person": False, "mask_company": True}
_TAG = re.compile(r"\[\[?\s*([A-Za-z]+)\s*[_\- ]?\s*(\d+)\s*\]?\]")
_CODE_TO_LABEL = {v: k for k, v in PLACEHOLDER.items()}


def should_mask(label: str, policy: dict) -> bool:
    tier = TIER.get(label, 3)
    if tier == 1:
        return policy.get("mask_company", True) if label == "company" else True
    if tier == 2:
        return bool(policy.get("mask_person", False))
    return False


def _as_span(sp):
    if isinstance(sp, Span):
        return sp
    return Span(sp["start"], sp["end"], sp["text"], sp["label"], list(sp.get("sources", [])))


def mask(text: str, spans, policy: dict | None = None) -> dict:
    policy = {**DEFAULT_POLICY, **(policy or {})}
    spans = sorted((_as_span(s) for s in spans), key=lambda s: (s.start, -s.end))
    out, pos, mapping, ids, counters, entries, unmasked = [], 0, {}, {}, {}, [], []
    for s in spans:
        if s.start < pos:  # 겹치는 구간은 앞의(긴) 구간이 이미 덮었다
            continue
        surface = text[s.start:s.end]
        if not should_mask(s.label, policy):
            unmasked.append({"start": s.start, "end": s.end, "text": surface, "label": s.label,
                             "reason": f"등급 {TIER.get(s.label, 3)} 정책으로 가리지 않음"})
            continue
        key = (s.label, surface)
        if key not in ids:
            counters[s.label] = counters.get(s.label, 0) + 1
            ids[key] = counters[s.label]
        tag = f"[[{PLACEHOLDER.get(s.label, 'X')}_{ids[key]}]]"
        mapping[tag] = surface
        out.append(text[pos:s.start])
        out.append(tag)
        pos = s.end
        entries.append({"start": s.start, "end": s.end, "text": surface, "label": s.label, "placeholder": tag})
    out.append(text[pos:])
    return {"masked": "".join(out), "mapping": mapping, "entries": entries, "unmasked": unmasked, "policy": policy}


def restore(answer: str, mapping: dict) -> str:
    """외부 응답의 자리표를 원문으로. 모르는 자리표는 그대로 둔다(추측해 채우지 않는다)."""
    norm = {}
    for tag, original in mapping.items():
        m = _TAG.fullmatch(tag)
        if m:
            norm[(m.group(1).upper(), m.group(2))] = original

    def rep(m):
        return norm.get((m.group(1).upper(), m.group(2)), m.group(0))

    return _TAG.sub(rep, answer)


def instruction_for_external(lang: str = "ko") -> str:
    # 11-03 외부 호출 점검: Sonnet 이 답변 끝에 "자리표를 그대로 두었다"는 주석을 붙여 복원 뒤 어색했다 → 주석 금지 문장 추가
    if lang == "en":
        return ("Tokens like [[ORG_1]] or [[AMT_2]] are redaction placeholders. Keep every placeholder exactly as written "
                "in your answer, do not guess what it stands for, and do not mention or explain the placeholders in your answer.")
    return ("본문의 [[ORG_1]], [[AMT_2]] 같은 표기는 가려진 자리표입니다. 답변(번역·요약 포함)에서도 자리표를 글자 그대로 유지하고, "
            "무엇인지 추측해 채우지 마세요. 자리표에 대한 설명이나 주석은 답변에 넣지 마세요.")


if __name__ == "__main__":
    import sys
    from common import utf8_stdout
    from detect import detect
    utf8_stdout()
    t = sys.stdin.read() if not sys.stdin.isatty() else (
        "고객사 (주)한빛에어로 KX-3 브래킷(품번 BRK-1120-03A) 단가 850,000원, 담당 김지영 과장(010-4821-7736). 한빛에어로 감사 대응용으로 번역해 주세요.")
    d = detect(t, use_llm=False)
    m = mask(t, d["spans"])
    print(m["masked"])
    print(m["mapping"])
    print("복원 일치:", restore(m["masked"], m["mapping"]) == t)
