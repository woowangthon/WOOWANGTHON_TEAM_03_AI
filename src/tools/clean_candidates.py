"""밤 배치가 만든 샘플·공격 후보를 기계적으로 정리해 사람 검토 양을 줄인다.

하는 일
- 구간 교정: "이름 직함 번호"를 사람+연락처로 분리, "프로젝트 코드:" 접두 제거, 프로젝트 코드 꼴은 doc_no로, 공개 규격(ISO 등)은 제거,
  사람 구간은 이름만, 변형 표기(전각·공백·하이픈 제거)는 본문의 실제 표기로 교정. 그래도 본문에 없으면 버리고 '수동' 표시.
- 누락 보완: 규칙 탐지기가 잡은 구간(번호·금액·연락처·사전·사람 단서)이 정답에 없으면 자동 추가하고 표시.
- 경로 교정(샘플): 본문에 '외부 공유 금지·내부 공유용' 같은 말이 있는데 route=external이면 local로.
- 중복 교체(샘플): 기존 10개와 후보 사이에서 반복되는 회사명·사람·사업자번호를 새 값으로 바꿈(본문·구간 동시).
- 기대 결과(공격): 기법에 '통째'가 있으면 block, 아니면 mask. 비슷한 후보(3-gram 유사도)는 중복 표시.
- 검토표(md + PDF)와 정리본 jsonl 저장. 정리본은 eval.py가 바로 읽을 수 있는 형식.

사용: python src/tools/clean_candidates.py [--samples 후보.jsonl] [--attacks 후보.jsonl] [--doc "검토표.md"]
"""
import argparse
import json
import random
import re
import sys
from collections import Counter
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from common import DATA, ROOT, find_all, load_samples, utf8_stdout  # noqa: E402
from detect_rules import detect_rules, normalize  # noqa: E402

TITLE = r"(?:과장|대리|부장|차장|사원|팀장|주임|이사|상무|전무|책임자|책임|수석|선임|매니저|담당자|연구원|기사)"
STD = re.compile(r"^(?:ISO|IEC|ASTM|AWS|MIL|KS|EN|DIN|JIS|SAE|NAS|AMS|ANSI|API|AQAP|KDS)(?![A-Za-z])", re.I)
CODE = re.compile(r"^(?:[A-Z]{1,4}\d?-\d{2,4}-\d{2,5}(?:-\d{2,5})?[A-Z]?|\d{4}-[A-Z]{1,4}-\d{2,5}|[A-Z]{2,4}-[A-Z]\d-\d{4}-\d{2})$")
PREFIX = re.compile(r"^(?:프로젝트\s*(?:ID|코드|번호)|문서\s*번호|도면\s*번호|개정\s*번호|사업자\s*번호)\s*[:：]?\s*")
NAME_TITLE_NUM = re.compile(r"^([가-힣]{2,4})\s*" + TITLE + r"?\s*[,，]?\s*(\(?[\d０-９－\-\s]{9,14}\)?)?$")
NAME_TITLE = re.compile(r"^([가-힣]{2,4})\s+" + TITLE + r"$")
INTERNAL = re.compile(r"외부\s*(?:공유|전송|공개|유출)\s*(?:는\s*|은\s*)?(?:금지|불가)|내부\s*(?:공유|회의|비공개|기밀|보안)|내부만|사내\s*공유")
BLOCK_TEXT = re.compile(r"(?:전체|모든|전부)\s*(?:정보|리스트|목록|견적표|내용|견적\s*정보)?\s*(?:를|을)?\s*(?:정리|표로|리스트|문서화)")

COMPANY_POOL = ["태성정공", "유진에어로텍", "삼우메탈", "경도시스템", "서해항공부품", "미래정밀", "대원테크닉스", "한울시스템즈",
                "청운정밀", "에이원메탈", "보성에어로", "신광테크", "금강정공", "동서항공기술", "누리메탈", "선일정밀"]
PERSON_POOL = ["박서연", "이도현", "정하윤", "최준혁", "강민재", "윤지호", "장예린", "임태양", "한소율", "오승우", "서지안", "문가은",
               "배수아", "신재원", "권나연", "조현우"]
random.seed(20261029)


def norm_key(s: str) -> str:
    return re.sub(r"[\s\-,.()]", "", normalize(s)).lower()


def find_variant(text: str, t: str):
    """t의 변형 표기(전각, 공백, 하이픈·쉼표 유무)가 본문에 있으면 그 (start, end)를 돌려준다."""
    key = norm_key(t)
    if len(key) < 3:
        return None
    n = len(text)
    for i in range(n):
        if normalize(text[i]) in " \t\n-,.()":
            continue
        acc = ""
        for j in range(i, min(n, i + len(t) * 3 + 8)):
            ch = normalize(text[j])
            if ch in " \t\n-,.()":
                continue
            acc += ch.lower()
            if acc == key:
                return i, j + 1
            if not key.startswith(acc):
                break
    return None


def overlaps(a, b):
    return a[0] < b[1] and b[0] < a[1]


def fix_spans(text: str, spans: list):
    """정답 구간을 교정한다. (새 구간 리스트, 자동 메모, 수동 메모) 반환. 구간은 {"text","label"}."""
    auto, manual, out = [], [], []
    for sp in spans:
        t = str(sp.get("text", "")).strip()
        label = sp.get("label", "other")
        cands = []  # (text, label)
        if find_all(text, t):
            cands.append((t, label))
        else:
            t2 = PREFIX.sub("", t)
            m = NAME_TITLE_NUM.match(t)
            if t2 != t and find_all(text, t2):
                cands.append((t2, label)); auto.append(f"접두 제거: {t} → {t2}")
            elif m and (m.group(2) or NAME_TITLE.match(t)):
                name = m.group(1)
                num = (m.group(2) or "").strip("() ")
                if find_all(text, name):
                    cands.append((name, "person"))
                if num and find_all(text, num):
                    cands.append((num, "contact"))
                if cands:
                    auto.append(f"이름/번호 분리: {t} → " + " + ".join(c[0] for c in cands))
                else:
                    manual.append(f"본문에 없음: {t}")
            else:
                pos = find_variant(text, t)
                if pos:
                    v = text[pos[0]:pos[1]]
                    cands.append((v, label)); auto.append(f"변형 표기로 교정: {t} → {v}")
                else:
                    manual.append(f"본문에 없음(변형 표기 수동 확인): {t}({label})")
        for ct, cl in cands:
            if STD.match(ct):
                auto.append(f"공개 규격 제외: {ct}"); continue
            if cl != "doc_no" and CODE.match(ct):
                auto.append(f"{cl}→doc_no: {ct}"); cl = "doc_no"
            if cl == "contact" and re.fullmatch(r"[가-힣]{2,4}(?:\s*" + TITLE + ")?", ct):
                nm = re.match(r"[가-힣]{2,4}", ct).group(0)
                auto.append(f"contact→person: {ct} → {nm}"); ct, cl = nm, "person"
            if cl == "person":
                m2 = NAME_TITLE.match(ct)
                if m2:
                    auto.append(f"직함 제거: {ct} → {m2.group(1)}"); ct = m2.group(1)
            if cl == "project" and re.search(r"\d{3,}", ct) and not re.search(r"[가-힣]", ct):
                auto.append(f"project→doc_no: {ct}"); cl = "doc_no"
            out.append({"text": ct, "label": cl})
    # 중복 제거
    seen, uniq = set(), []
    for sp in out:
        k = (sp["text"], sp["label"])
        if k not in seen:
            seen.add(k); uniq.append(sp)
    return uniq, auto, manual


def positions(text, spans):
    pos = []
    for sp in spans:
        pos += find_all(text, sp["text"])
    return pos


def add_missing(text: str, spans: list):
    """규칙 탐지가 잡았는데 정답에 없는 구간을 추가한다."""
    auto = []
    pos = positions(text, spans)
    for rs in detect_rules(text):
        if any(overlaps((rs.start, rs.end), p) for p in pos):
            continue
        if any(sp["text"] == rs.text for sp in spans):
            continue
        spans.append({"text": rs.text, "label": rs.label})
        pos.append((rs.start, rs.end))
        auto.append(f"자동 추가({rs.sources[0].split(':')[1]}): {rs.text}({rs.label})")
    return spans, auto


def trigrams(s):
    s = re.sub(r"\s+", " ", s)
    return {s[i:i + 3] for i in range(max(0, len(s) - 2))}


def jaccard(a, b):
    return len(a & b) / len(a | b) if a or b else 0.0


def clean_samples(items, base):
    used_company = Counter(sp["text"] for b in base for sp in b["spans"] if sp["label"] == "company")
    used_person = Counter(sp["text"] for b in base for sp in b["spans"] if sp["label"] == "person")
    used_biz = Counter(sp["text"] for b in base for sp in b["spans"] if sp["label"] == "biz_no")
    cpool, ppool = list(COMPANY_POOL), list(PERSON_POOL)
    out = []
    for it in items:
        text = it["text"]
        spans, auto, manual = fix_spans(text, it.get("spans", []))
        spans, auto2 = add_missing(text, spans)
        auto += auto2
        route, category = it.get("route", "external"), it.get("category", "sensitive")
        if route == "external" and INTERNAL.search(text):
            auto.append(f"경로 변경 external→local: 본문 '{INTERNAL.search(text).group(0)}'")
            route, category = "local", "local"
        # 중복 이름 교체
        for sp in list(spans):
            v, lb = sp["text"], sp["label"]
            repl = None
            if lb == "company" and used_company[v] and cpool:
                repl = cpool.pop(0)
            elif lb == "person" and used_person[v] and ppool:
                repl = ppool.pop(0)
            elif lb == "biz_no" and used_biz[v]:
                repl = f"{random.randint(101, 899)}-{random.randint(10, 89)}-{random.randint(10000, 99999)}"
            if repl:
                text = text.replace(v, repl)
                for s2 in spans:
                    s2["text"] = s2["text"].replace(v, repl)
                auto.append(f"중복 교체: {v} → {repl}")
                v = repl
            if lb == "company":
                used_company[v] += 1
            elif lb == "person":
                used_person[v] += 1
            elif lb == "biz_no":
                used_biz[v] += 1
        if category == "local" and "회의록" in text:
            manual.append("유형 중복: 회의록 요약 (다른 작업으로 바꾸면 좋음)")
        if category == "sensitive" and len(spans) < 2:
            manual.append("sensitive인데 구간 2개 미만")
        # 최종 검증
        bad = [sp["text"] for sp in spans if not find_all(text, sp["text"])]
        if bad:
            manual.append(f"검증 실패: {bad}")
            spans = [sp for sp in spans if find_all(text, sp["text"])]
        out.append({"id": it["id"], "category": category, "route": route, "text": text, "spans": spans,
                    "note": it.get("note", ""), "review": {"auto": auto, "manual": manual},
                    "status": "검토 필요" if manual else "자동 정리됨"})
    return out


def clean_attacks(items):
    out, seen_grams = [], []
    for it in items:
        text = it["text"]
        spans, auto, manual = fix_spans(text, it.get("spans", []))
        spans, auto2 = add_missing(text, spans)
        auto += auto2
        tech = it.get("technique", "")
        expected = "block" if ("통째" in tech or BLOCK_TEXT.search(text)) else "mask"
        if expected != it.get("expected"):
            auto.append(f"기대 결과 {it.get('expected')}→{expected}")
        g = trigrams(text)
        for pid, pg in seen_grams:
            sim = jaccard(g, pg)
            if sim >= 0.6:
                manual.append(f"중복: {pid}와 유사도 {sim:.2f} (다른 기법으로 교체 권장)")
                break
        seen_grams.append((it["id"], g))
        bad = [sp["text"] for sp in spans if not find_all(text, sp["text"])]
        if bad:
            manual.append(f"검증 실패: {bad}")
            spans = [sp for sp in spans if find_all(text, sp["text"])]
        out.append({"id": it["id"], "category": "attack", "route": "block" if expected == "block" else "external",
                    "technique": tech, "expected": expected, "source": it.get("source"), "text": text, "spans": spans,
                    "note": "", "review": {"auto": auto, "manual": manual},
                    "status": "검토 필요" if manual else "자동 정리됨"})
    return out


def write_jsonl(path, rows):
    with open(path, "w", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")


def item_md(r):
    head = f"### {r['id']} · {r['category']}/{r['route']}"
    if r.get("technique"):
        head += f" · 기법: {r['technique']} · 기대: {r['expected']}"
    head += f" · **{r['status']}**"
    lines = [head, "", "- 본문: " + r["text"].replace("\n", " ⏎ ")]
    lines.append("- 구간: " + (" · ".join(f"{sp['label']}:{sp['text']}" for sp in r["spans"]) or "(없음)"))
    if r["review"]["auto"]:
        lines.append("- 자동 정리: " + " / ".join(r["review"]["auto"]))
    if r["review"]["manual"]:
        lines.append("- **확인 필요**: " + " / ".join(r["review"]["manual"]))
    return "\n".join(lines) + "\n"


def main():
    utf8_stdout()
    cdir = DATA / "candidates"
    ap = argparse.ArgumentParser()
    ap.add_argument("--samples", default=str(sorted(cdir.glob("samples_candidates_*.jsonl"))[-1]))
    ap.add_argument("--attacks", default=str(sorted(cdir.glob("attack_candidates_*.jsonl"))[-1]))
    ap.add_argument("--doc", default=str(ROOT.parent / f"후보 검토표 ({datetime.now():%Y-%m-%d}).md"))
    args = ap.parse_args()
    stamp = datetime.now().strftime("%Y%m%d_%H%M")

    base = load_samples(DATA / "samples.jsonl")
    samples = clean_samples(load_samples(Path(args.samples)), base)
    attacks = clean_attacks(load_samples(Path(args.attacks)))
    sp_path = cdir / f"samples_clean_{stamp}.jsonl"
    at_path = cdir / f"attacks_clean_{stamp}.jsonl"
    write_jsonl(sp_path, samples)
    write_jsonl(at_path, attacks)

    def stats(rows):
        c = Counter(r["status"] for r in rows)
        return f"{len(rows)}건 (자동 정리됨 {c['자동 정리됨']}, 검토 필요 {c['검토 필요']})"

    md = [f"# 후보 검토표 ({datetime.now():%Y-%m-%d})", "",
          "30B가 만든 후보를 스크립트가 1차 정리한 결과다. '자동 정리' 줄은 스크립트가 바꾼 것, '확인 필요' 줄은 사람이 봐야 하는 것. "
          "확인 필요가 없는 건도 본문과 구간이 자연스러운지 한 번은 읽어야 한다. 기준: 회사명·사업명·식별번호·금액·사람·연락처·사업자번호는 구간, "
          "공개 규격 번호(MIL/ISO/ASTM/AWS/KS)·치수·수량·날짜는 구간이 아님. 사람 구간은 이름만(직함 제외), 성+직함('박 대리')은 통째로.", "",
          f"- 샘플 후보: {stats(samples)} → `{sp_path.name}`",
          f"- 공격 후보: {stats(attacks)} → `{at_path.name}`", "",
          "검토 후 할 일: 틀린 구간은 jsonl에서 고치고, 버릴 건은 줄을 지운다. 샘플은 기존 10개(S01~S10)와 합쳐 50개가 목표, 공격은 30개.", "",
          "## 샘플 후보", ""]
    md += [item_md(r) for r in samples]
    md += ["## 공격 후보", "", "기대 결과: mask = 구간을 가리고 외부로 보내야 함, block = 통째 유출 요청이라 차단해야 함.", ""]
    md += [item_md(r) for r in attacks]
    Path(args.doc).write_text("\n".join(md), encoding="utf-8")

    print("샘플:", stats(samples)); print("공격:", stats(attacks))
    print("저장:", sp_path); print("저장:", at_path); print("검토표:", args.doc)
    for r in samples + attacks:
        if r["review"]["manual"]:
            print(f"  [검토] {r['id']}: " + " / ".join(r["review"]["manual"]))


if __name__ == "__main__":
    main()
