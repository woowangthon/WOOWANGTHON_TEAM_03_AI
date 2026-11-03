"""가림·복원 (mask.py): 등급 정책, 같은 표기 같은 자리표, 복원 왕복, 자리표 변형 복원."""
from common import Span
from mask import PLACEHOLDER_RE, instruction_for_external, mask, restore

TEXT = ("고객사 (주)한빛에어로 KX-3 브래킷(품번 BRK-1120-03A) 단가 850,000원, 담당 김지영 과장(010-4821-7736). "
        "한빛에어로 감사 대응용으로 번역해 주세요.")


def span(text, sub, label, nth=0):
    start = -1
    for _ in range(nth + 1):
        start = text.find(sub, start + 1)
    assert start >= 0, sub
    return Span(start, start + len(sub), sub, label, ["gold"])


SPANS = [span(TEXT, "한빛에어로", "company"), span(TEXT, "KX-3", "project"), span(TEXT, "BRK-1120-03A", "doc_no"),
         span(TEXT, "850,000원", "price"), span(TEXT, "김지영", "person"), span(TEXT, "010-4821-7736", "contact"),
         span(TEXT, "한빛에어로", "company", nth=1)]


def test_default_policy_masks_tier1_and_keeps_names():
    m = mask(TEXT, SPANS)
    for value in ("한빛에어로", "KX-3", "BRK-1120-03A", "850,000원", "010-4821-7736"):
        assert value not in m["masked"]
    assert "김지영 과장" in m["masked"]  # 등급 2(이름)는 기본 끔, 직급은 등급 3
    assert [u["label"] for u in m["unmasked"]] == ["person"] and "등급 2" in m["unmasked"][0]["reason"]


def test_same_surface_gets_same_placeholder():
    m = mask(TEXT, SPANS)
    assert m["masked"].count("[[ORG_1]]") == 2 and m["mapping"]["[[ORG_1]]"] == "한빛에어로"
    assert set(m["mapping"]) == {"[[ORG_1]]", "[[PROJECT_1]]", "[[ID_1]]", "[[AMT_1]]", "[[CONTACT_1]]"}


def test_restore_round_trip_equals_original():
    m = mask(TEXT, SPANS)
    assert restore(m["masked"], m["mapping"]) == TEXT


def test_policy_toggles():
    on = mask(TEXT, SPANS, {"mask_person": True})
    assert "[[PERSON_1]] 과장" in on["masked"] and "김지영" not in on["masked"]
    assert restore(on["masked"], on["mapping"]) == TEXT
    off = mask(TEXT, SPANS, {"mask_company": False})
    assert "한빛에어로" in off["masked"] and "[[ORG_1]]" not in off["masked"]


def test_restore_accepts_placeholder_variants_and_keeps_unknown():
    mapping = {"[[ORG_1]]": "한빛에어로", "[[AMT_2]]": "850,000원"}
    out = restore("A [[ ORG_1 ]] B [ORG_1] C [[org-1]] D [[AMT_2]] E [[ID_9]]", mapping)
    assert out == "A 한빛에어로 B 한빛에어로 C 한빛에어로 D 850,000원 E [[ID_9]]"


def test_overlapping_spans_keep_the_first_longer_one():
    text = "품번 BRK-1120-03A 입니다"
    m = mask(text, [span(text, "BRK-1120-03A", "doc_no"), span(text, "1120-03A", "doc_no")])
    assert m["masked"] == "품번 [[ID_1]] 입니다" and len(m["entries"]) == 1


def test_external_instruction_mentions_placeholders_and_forbids_commentary():
    ko, en = instruction_for_external(), instruction_for_external("en")
    assert "[[ORG_1]]" in ko and "주석" in ko
    assert "placeholder" in en.lower() and "do not mention" in en.lower()


def test_placeholder_regex_matches_only_tags():
    found = [m.group(0) for m in PLACEHOLDER_RE.finditer("x [[ORG_1]] y [[AMT_12]] z [[not]]")]
    assert found == ["[[ORG_1]]", "[[AMT_12]]"]
