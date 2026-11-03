"""detect.py 의 순수 함수: 긴 글 분할, 지시 삽입 문장 지우기, 30B 구간 상식 필터, 병합, 다듬기, 전파, 프롬프트 선택.
30B 호출 자체(detect(use_llm=True))는 Ollama 가 필요해 여기서 다루지 않는다."""
from common import Span
from detect import (blank_injections, context_filter, merge_spans, prompt_for, propagate, sanity_filter, split_chunks,
                    trim_spans)
from detect_llm import SYSTEM_PROMPT


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


def test_propagate_skips_llm_only_projects_and_frequent_terms():
    text = " ".join(["규격 구절"] * 12)
    assert len(propagate(text, [sp(text, "규격 구절", "project", ["llm"])])) == 1
    assert len(propagate(text, [sp(text, "규격 구절", "company", ["llm"])])) == 1  # 사전 밖 표기가 10회 넘으면 전파하지 않는다


def test_prompt_for_modes():
    rules = [Span(0, 4, "KX-3", "project", ["dict:projects.txt"])]
    assert prompt_for(rules, "A") == SYSTEM_PROMPT
    c = prompt_for(rules, "C")
    assert c.startswith(SYSTEM_PROMPT) and "KX-3(project)" in c and "규칙이 놓친" in c
    assert "없음" in prompt_for([], "C")
