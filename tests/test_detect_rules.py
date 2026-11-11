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


def test_common_words_after_person_cue_are_not_names():
    # 11-11 K-51~53: 단서어 뒤의 일반 낱말을 이름으로 잡았고 전파가 문서 전체로 퍼뜨렸다
    got = pairs("생산기술 담당은 변경사항의 적용범위를 확인하였다. 별도 담당자가 대조하여 누락된 이동 기록을 처리하였다. "
                "장비 담당자가 현품 위치변경을 작업대장에 기입했다. 미정리 항목은 책임 작업자에게 재확인을 요청하였다. "
                "생산 책임자\n승인담당 확인 후 차기 작업에 적용하도록 정리했다. 승인 범위를 과장하지 않는다.")
    assert not [p for p in got if p[0] == "person"]


def test_names_in_table_cells_keep_their_surname():
    got = pairs("현장 담당   강미온   작업배치\n계측자   노유원   조치 검토\n실무 검수자   주연담   추가 분석\n"
                "담당 이다희 대리, 담당 이민수(품질팀), 검토자 허준 과장, 담당자는 나지아입니다.")
    assert {("person", "강미온"), ("person", "노유원"), ("person", "주연담"), ("person", "이다희"), ("person", "이민수"),
            ("person", "허준"), ("person", "나지아")} <= got
    assert ("person", "다희") not in got and ("person", "민수") not in got


def test_person_shape_check_keeps_names_and_titles():
    for ok in ("나지아", "해도준", "남궁민수", "허준", "박 대리", "김철수님", "Kim Minsoo", "박지훈 대리"):
        assert dr._person_ok(ok), ok
    for bad in ("변경사항", "대조하여", "승인담당", "항목은", "범위를", "확인하지"):
        assert not dr._person_ok(bad), bad


def test_letter_letter_number_codes_are_doc_numbers():
    # 11-11 K-51: 작업지시 번호 18개 중 하나를 30B 가 놓쳤고 이 꼴은 규칙이 없었다
    got = pairs("작업지시 번호   HFQ-WO-118   전표 대조, 결함 기호 NC-HFQ-214, 기준 IPC-A-610 및 MIL-STD-810")
    assert {("doc_no", "HFQ-WO-118"), ("doc_no", "NC-HFQ-214")} <= got
    assert not [p for p in got if p[1] in ("IPC-A-610", "MIL-STD-810")]
