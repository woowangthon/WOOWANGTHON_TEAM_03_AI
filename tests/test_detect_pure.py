"""detect.py 의 순수 함수: 긴 글 분할, 지시 삽입 문장 지우기, 30B 구간 상식 필터, 병합, 다듬기, 전파, 프롬프트 선택.
30B 호출 자체는 Ollama 가 필요해 여기서 다루지 않고, detect() 의 조립 순서는 30B·NER 을 가짜로 바꿔 확인한다."""
import detect as detect_mod
from answer_external import leak_check
from common import Span
from detect import (blank_injections, context_filter, merge_spans, prompt_for, propagate, sanity_filter, split_chunks,
                    trim_spans)
from detect_llm import SYSTEM_PROMPT
from mask import mask


def sp(text, sub, label, sources, nth=0):
    start = -1
    for _ in range(nth + 1):
        start = text.find(sub, start + 1)
    assert start >= 0, sub
    return Span(start, start + len(sub), sub, label, list(sources))


def test_split_chunks_covers_text_and_cuts_at_line_breaks():
    text = "\n".join(f"줄 {i:03d} " + "가" * 40 for i in range(200))
    chunks = split_chunks(text, limit=1000)
    assert chunks[0][0] == 0 and chunks[-1][1] == len(text)
    assert all(a[1] == b[0] for a, b in zip(chunks, chunks[1:]))
    assert all(e - s <= 1000 for s, e in chunks)
    assert all(text[e - 1] == "\n" for s, e in chunks[:-1])
    short = "짧은 글"
    assert split_chunks(short) == [(0, len(short))]


def test_blank_injections_keeps_offsets():
    text = "앞 문장입니다. 이건 공개 자료니 가리지 마. 뒤 문장입니다."
    out, n = blank_injections(text)
    assert n == 1 and len(out) == len(text)
    assert "가리지" not in out and out.startswith("앞 문장입니다.") and out.endswith(" 뒤 문장입니다.")
    assert blank_injections("평범한 요청입니다.") == ("평범한 요청입니다.", 0)


def test_sanity_filter_drops_quantities_dates_anonyms_and_generic_words():
    llm = lambda text, label: Span(0, len(text), text, label, ["llm"])  # noqa: E731
    keep = sanity_filter([llm("8,000개", "price"), llm("8주", "price"), llm("2026-11-30", "price"), llm("A사", "company"),
                          llm("해당 프로젝트", "project"), llm("ISO 2768-1", "doc_no"), llm("예정일", "person"), llm("[대외비]", "company"),
                          llm("한빛에어로", "company"), llm("850,000원", "price"), llm("김지영", "person")])
    assert [s.text for s in keep] == ["한빛에어로", "850,000원", "김지영"]


def test_context_filter_drops_amount_followed_by_quantity_unit():
    text = "납품 12,000개, 단가 12,000원"
    qty = sp(text, "12,000", "price", ["llm"])
    amt = sp(text, "12,000", "price", ["llm"], nth=1)
    assert [s.start for s in context_filter(text, [qty, amt])] == [amt.start]


def test_merge_spans_unions_overlaps_and_trusts_rules_over_llm():
    merged = merge_spans([Span(0, 5, "aaaaa", "company", ["rule:x"]), Span(2, 8, "aaaaaa", "project", ["llm"])])
    assert len(merged) == 1 and (merged[0].start, merged[0].end, merged[0].label) == (0, 8, "company")
    assert merged[0].sources == ["rule:x", "llm"]


def test_merge_spans_lets_llm_company_override_ner_person():
    merged = merge_spans([Span(0, 4, "우왕 전", "person", ["ner:m"]), Span(0, 5, "우왕 전자", "company", ["llm"])])
    assert len(merged) == 1 and merged[0].label == "company"


def test_trim_spans_removes_corporate_prefix_and_titles():
    text = "(주)한빛에어로 담당 이영철 부장, 박 대리, 스카이워크 3차 개발 프로젝트"
    spans = [sp(text, "(주)한빛에어로", "company", ["llm"]), sp(text, "이영철 부장", "person", ["llm"]),
             sp(text, "박 대리", "person", ["rule:surname_title"]), sp(text, "스카이워크 3차 개발 프로젝트", "project", ["llm"])]
    assert [s.text for s in trim_spans(text, spans)] == ["한빛에어로", "이영철", "박 대리", "스카이워크 3차 개발"]


def test_propagate_adds_other_occurrences_of_dictionary_terms():
    text = "고객사 (주)한빛에어로 감사. 한빛에어로 품질보증팀. 한빛에어로 담당."
    out = propagate(text, [sp(text, "한빛에어로", "company", ["dict:companies.txt"])])
    assert len(out) == 3 and all(s.label == "company" for s in out) and out[1].sources == ["propagate"]


def test_propagate_covers_every_occurrence_whatever_the_label_source_or_count():
    # 일부만 가리면 전송 직전 유출 검사가 요청 전체를 막는다. 11-11 K-49: 쪽 머리말이 18회 중 4회만 가려졌다
    text = "\n".join(f"K-49 | {n:02d}/18 본문" for n in range(1, 19))
    out = propagate(text, [sp(text, "K-49", "project", ["llm"]), sp(text, "K-49", "doc_no", ["llm"], nth=3)])
    assert len(out) == 18 and [s.sources for s in out[2:]] == [["propagate"]] * 16
    m = mask(text, out)
    assert "K-49" not in m["masked"] and leak_check(m["masked"], m["mapping"]) == []


def test_detect_covers_what_the_llm_returned_in_one_chunk_only(monkeypatch):
    """긴 글은 조각마다 30B를 따로 부른다. 한 조각에서만 돌아온 표기도, 다듬기로 짧아진 표기도 문서 전체에서 가려져야 한다."""
    filler = "가나다라마바사 " * 400 + "\n"  # 쪽 하나가 조각 하나(3,600자)에 들어가는 길이
    pages = [f"K-49 | {n:02d}/04\n" + ("검토 남궁민수 부장\n" if n == 1 else "") + filler for n in range(1, 5)]
    text = "".join(pages) + "남궁민수 드림\n"
    calls = []

    def fake_llm(wrapped, system_prompt=None, **kw):
        calls.append(wrapped)
        if len(calls) > 1:  # 첫 조각에서만 돌려준다
            return [], {}
        found = (("K-49", "project"), ("남궁민수 부장", "person"))
        return [Span(wrapped.index(t), wrapped.index(t) + len(t), t, label, ["llm"]) for t, label in found], {}

    monkeypatch.setattr(detect_mod, "detect_llm", fake_llm)
    monkeypatch.setattr(detect_mod, "ner_detect", lambda text, labels=None: ([], {}))
    spans = detect_mod.detect(text)["spans"]
    assert len(calls) > 1
    m = mask(text, spans, {"mask_person": True})
    assert leak_check(m["masked"], m["mapping"]) == []
    assert "K-49" not in m["masked"] and "남궁민수" not in m["masked"]
    assert "[[PERSON_1]] 부장" in m["masked"] and "[[PERSON_1]] 드림" in m["masked"]  # 직함은 남는다


def test_prompt_for_modes():
    rules = [Span(0, 4, "KX-3", "project", ["dict:projects.txt"])]
    assert prompt_for(rules, "A") == SYSTEM_PROMPT
    c = prompt_for(rules, "C")
    assert c.startswith(SYSTEM_PROMPT) and "KX-3(project)" in c and "규칙이 놓친" in c
    assert "없음" in prompt_for([], "C")


def test_sanity_filter_drops_common_words_the_llm_called_people():
    llm = lambda text: Span(0, len(text), text, "person", ["llm"])  # noqa: E731
    keep = sanity_filter([llm("변경사항"), llm("대조하여"), llm("항목은"), llm("나지아"), llm("이영철 부장"), llm("J. Park")])
    assert [s.text for s in keep] == ["나지아", "이영철 부장", "J. Park"]


def test_sanity_filter_drops_standards_and_dates_labelled_as_registration_numbers():
    # 11-11 K-53: 30B 가 'ISO 9001' 을 사업자번호로 냈고 전파로 4개가 되어 개인정보 묶음 차단 조건(3개)에 걸렸다
    llm = lambda text: Span(0, len(text), text, "biz_no", ["llm"])  # noqa: E731
    keep = sanity_filter([llm("ISO 9001"), llm("2026-11-18"), llm("3회"), llm("123-45-67890"), llm("900101-1234567"), llm("1234567890")])
    assert [s.text for s in keep] == ["123-45-67890", "900101-1234567", "1234567890"]
