"""공개 한국어 NER(토큰 분류) 모델을 세 번째 탐지기로 쓰기 위한 모듈. CPU, 문장당 수 ms.

10-29 프로브: atonlee/koelectra-ko-pii-ner 가 김지영·박성호(NAME 0.99), 010-… (PHONE 0.99), J. Park(NAME 0.95)을 잡음.
Leo97/KoELECTRA-small-v3-modu-ner 는 PS(사람)·OG(회사) 등 일반 개체. 둘 다 회사명은 부분 구간(한빛에, 한빛)으로 끊는 경향.
transformers/torch가 없으면 available()이 False이고 ner_detect()는 빈 목록을 돌려준다.
"""
import re
import time

from common import Span

DEFAULT_MODEL = "atonlee/koelectra-ko-pii-ner"
# 모델 라벨 → 우리 라벨. 없는 것은 버린다. (PHONE/EMAIL/RRN 등은 규칙이 이미 잡지만 비교용으로 매핑해 둔다)
LABEL_MAP = {
    "NAME": "person", "PS": "person", "PER": "person", "PERSON": "person",
    "ORGANIZATION": "company", "OG": "company", "ORG": "company",
    "PHONE": "contact", "EMAIL": "contact", "ADDRESS": "contact",
    "RRN": "biz_no", "ACCOUNT_NUMBER": "biz_no", "CARD_NUMBER": "biz_no", "PASSPORT": "biz_no", "DRIVER_LICENSE": "biz_no",
}
MAX_CHARS = 700  # 모델 입력 512토큰 한계. 줄 단위로 묶어 이 길이 안에서 끊는다.
_PIPES = {}
# 사람 이름 구조 검사. 밤 배치 3 ⑥·④에서 모델이 기술 용어(염수분무, 아노다이징), 도시(Gyeongju), 회사(Sungjin Precision Co.)를 NAME으로 냄.
SURNAMES = set("김이박최정강조윤장임한오서신권황안송류전홍고문양손배백허유남심노하곽성차주우구민진지엄채원천방공현함변염여추도소석선설마길연위표명기반왕금옥육인맹제모탁국어은편용예봉사부")
SURNAMES2 = {"황보", "남궁", "제갈", "사공", "선우", "독고", "서문", "동방"}
CORP_SUFFIX = re.compile(r"(?:Co\.?|Inc\.?|Ltd\.?|Corp\.?|GmbH|Company|Corporation|LLC)$", re.I)


def plausible_person(t: str, score: float, min_score: float) -> bool:
    """한글 이름은 성씨로 시작하는 2~3음절(복성이면 3~4음절), 영문 이름은 두 단어 이상·점수 0.9 이상·회사 접미 없음."""
    if re.fullmatch(r"[가-힣]+", t):
        if t[:2] in SURNAMES2:
            return 3 <= len(t) <= 4 and score >= min_score
        return 2 <= len(t) <= 3 and t[0] in SURNAMES and score >= min_score
    if re.search(r"[A-Za-z]", t):
        return len(t.split()) >= 2 and score >= 0.9 and not CORP_SUFFIX.search(t)
    return False


def available() -> bool:
    try:
        import torch  # noqa: F401
        import transformers  # noqa: F401
        return True
    except Exception:
        return False


def _pipe(model: str):
    if model not in _PIPES:
        from transformers import pipeline
        _PIPES[model] = pipeline("token-classification", model=model, aggregation_strategy="simple", device=-1)
    return _PIPES[model]


def _pieces(text: str, limit: int = MAX_CHARS):
    """(start, piece) 목록. 줄 단위로 묶고, 한 줄이 limit보다 길면 문장 단위로 더 쪼갠다."""
    out, buf, buf_start, pos = [], "", 0, 0
    for line in text.splitlines(keepends=True):
        if len(buf) + len(line) > limit and buf:
            out.append((buf_start, buf))
            buf, buf_start = "", pos
        if len(line) > limit:
            for m in re.finditer(r"[^.!?\n]+[.!?\n]?", line):
                out.append((pos + m.start(), m.group(0)))
            pos += len(line)
            buf_start = pos
            continue
        if not buf:
            buf_start = pos
        buf += line
        pos += len(line)
    if buf:
        out.append((buf_start, buf))
    return out


def ner_detect(text: str, model: str = DEFAULT_MODEL, min_score: float = 0.85, labels: tuple = ("person", "company")):
    """(spans, meta). spans는 Span(start, end, text, label, ["ner:<model>"]). 위치는 토크나이저 오프셋으로 원문 기준."""
    t0 = time.perf_counter()
    if not available():
        return [], {"error": "transformers/torch 없음", "total_s": 0.0}
    try:
        nlp = _pipe(model)
    except Exception as e:  # 모델 다운로드 실패 등
        return [], {"error": f"{type(e).__name__}: {str(e)[:150]}", "total_s": round(time.perf_counter() - t0, 3)}
    spans = []
    for start, piece in _pieces(text):
        if not piece.strip():
            continue
        for ent in nlp(piece):
            lab = LABEL_MAP.get(ent["entity_group"].split("-")[-1].upper())
            if lab is None or lab not in labels or ent["score"] < min_score:
                continue
            s, e = start + ent["start"], start + ent["end"]
            # 토크나이저 오프셋이 앞뒤 공백·구두점을 물고 올 수 있어 다듬는다
            while s < e and text[s] in " \t\n(（[":
                s += 1
            while e > s and text[e - 1] in " \t\n)）],.;:":
                e -= 1
            if e - s < 2:
                continue
            if lab == "person" and not plausible_person(text[s:e], ent["score"], min_score):
                continue
            spans.append(Span(s, e, text[s:e], lab, [f"ner:{model.split('/')[-1]}"]))
    spans.sort(key=lambda x: (x.start, -x.end))
    return spans, {"total_s": round(time.perf_counter() - t0, 3), "model": model}


if __name__ == "__main__":
    import sys
    from common import utf8_stdout
    utf8_stdout()
    sample = sys.stdin.read() if not sys.stdin.isatty() else (
        "안녕하세요, 품질팀 김지영입니다. 고객사 (주)한빛에어로 정민호 책임에게 회신했습니다. Contact: J. Park, Daesung Precision.")
    for m in (DEFAULT_MODEL, "Leo97/KoELECTRA-small-v3-modu-ner"):
        sp, meta = ner_detect(sample, model=m, labels=("person", "company", "contact"))
        print(m, meta, [(s.label, s.text) for s in sp])
