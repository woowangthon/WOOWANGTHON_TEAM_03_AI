"""규칙 탐지기 (detect_rules.py): 정규식 규칙별 적중, 공개 규격 제외, 사람 일반명사 제외, 사전 매칭, 전각 정규화."""
import pytest

import detect_rules as dr
from detect_rules import detect_rules, normalize


def pairs(text):
    return {(s.label, s.text) for s in detect_rules(text)}


def test_contacts_and_person_with_title():
    got = pairs("담당 박지훈 대리(010-2345-6789, jh.park@sejin-tech.co.kr)")
    assert ("contact", "010-2345-6789") in got and ("contact", "jh.park@sejin-tech.co.kr") in got
    assert ("person", "박지훈") in got


def test_business_and_resident_numbers():
    got = pairs("사업자등록번호 123-45-67890, 주민번호 900101-1234567")
    assert ("biz_no", "123-45-67890") in got and ("biz_no", "900101-1234567") in got


def test_hotline_and_voip_numbers_are_contacts():
    got = pairs("고객센터 1566-0000 · 1588-1234, 인터넷전화 070-7777-1234, 수신자부담 080-123-4567, 안심번호 0505-1234-5678")
    assert {("contact", "1566-0000"), ("contact", "1588-1234"), ("contact", "070-7777-1234"),
            ("contact", "080-123-4567"), ("contact", "0505-1234-5678")} <= got


def test_year_time_and_count_ranges_are_not_hotlines():
    got = pairs("1950-1999년 자료, 1600-1800시 사이, 1500-2000명 참가, 1800-2400원 구간, 품번 1700-1234")
    assert not [p for p in got if p[0] == "contact"]


def test_area_codes_with_parentheses():
    got = pairs("서울 (02) 555-0198, 대전 042)123-4567, 충북 043-222-1234, 경기 031-777-0215")
    assert {("contact", "02) 555-0198"), ("contact", "042)123-4567"), ("contact", "043-222-1234"), ("contact", "031-777-0215")} <= got


def test_document_codes_including_fullwidth_digits():
    got = pairs("도면 DWG-2025-0417, 품번 BRK-1120-03A, 전각 BRK－1120－03A, 로트 L240918-07")
    assert {("doc_no", "DWG-2025-0417"), ("doc_no", "BRK-1120-03A"), ("doc_no", "BRK－1120－03A"), ("doc_no", "L240918-07")} <= got


def test_public_standards_are_not_document_codes():
    got = pairs("규격은 ISO 2768-1 과 MIL-A-8625 Type II, AS9100D 를 따른다")
    assert not [p for p in got if p[0] == "doc_no"]


def test_prices_in_several_notations():
    got = pairs("단가 850,000원, 총액 $12,500, 지체상금은 32500원, 비용 팔십오만 원")
    assert {("price", "850,000원"), ("price", "$12,500"), ("price", "32500원"), ("price", "팔십오만 원")} <= got


def test_person_stop_words_are_not_names():
    got = pairs("담당자 정보는 아래와 같다. 담당자  예정일  진행 사항")
    assert not [p for p in got if p[0] == "person"]


@pytest.fixture
def temp_dict():
    base = list(dr.DICTS)
    dr.DICTS[:] = [
        ("companies.txt", "company", [(t, dr.term_regex(t)) for t in ("츄러스 공업", "Churros Industrial", "LIG넥스원", "LIG")]),
        ("projects.txt", "project", [(t, dr.term_regex(t)) for t in ("가온 사업",)]),
    ]
    yield
    dr.DICTS[:] = base


def test_dictionary_ignores_spaces_and_drops_contained_alias(temp_dict):
    got = pairs("츄러스공업과 churros industrial, LIG넥스원 납품분. 가온사업 보고")
    assert ("company", "츄러스공업") in got and ("company", "churros industrial") in got
    assert ("company", "LIG넥스원") in got and ("company", "LIG") not in got
    assert ("project", "가온사업") in got


def test_normalize_keeps_length_and_maps_fullwidth():
    s = "ＢＲＫ－１１２０　ａ–ｂ"
    assert len(normalize(s)) == len(s) and normalize(s) == "BRK-1120 a-b"
