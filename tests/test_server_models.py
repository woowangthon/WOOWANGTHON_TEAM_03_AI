"""모델 서비스 (server.py)의 입력 검증과 인증: 서버를 띄우지 않고 pydantic 모델과 키 검사 함수만 확인한다.
HTTP 수준 점검은 src/tools/server_check.py (Ollama 필요)."""
import pytest
from fastapi import HTTPException
from pydantic import ValidationError

import server
from common import Span


def test_text_or_body_exactly_one():
    assert server.TextIn(text="본문").composed() == ("본문", 0)
    assert server.TextIn(instruction="요약해 줘", body="본문").composed() == ("요약해 줘\n\n본문", 7)
    assert server.TextIn(body="본문").composed() == ("본문", 0)
    for bad in ({"text": "a", "body": "b"}, {}, {"text": "   "}):
        with pytest.raises(ValidationError):
            server.TextIn(**bad)


def test_analyze_defaults_and_route_variant_check():
    assert server.AnalyzeIn(text="x").policy.mask_person is False and server.AnalyzeIn(text="x").use_llm is True
    with pytest.raises(ValidationError):
        server.AnalyzeIn(text="x", route_variant="v9")


def test_answer_external_accepts_one_form_only():
    assert server.AnswerExternalIn(masked="[[ORG_1]]", mapping={"[[ORG_1]]": "a"}).fallback is True
    assert server.AnswerExternalIn(text="t", spans=[]).effort == "medium"
    for bad in ({"masked": "x", "mapping": {}, "text": "t", "spans": []}, {"masked": "x"}, {"text": "t"},
                {"masked": "x", "mapping": {}, "text": "t"}, {"masked": "x", "mapping": {}, "effort": "ultra"}):
        with pytest.raises(ValidationError):
            server.AnswerExternalIn(**bad)


def test_api_key_check():
    assert server.require_key("test-key") is None
    with pytest.raises(HTTPException) as e:
        server.require_key("wrong")
    assert e.value.status_code == 401
    with pytest.raises(HTTPException):
        server.require_key(None)


def test_span_out_adds_tier():
    assert server.span_out(Span(0, 4, "KX-3", "project", ["dict:projects.txt"]))["tier"] == 1
    assert server.span_out({"start": 0, "end": 3, "text": "김지영", "label": "person", "sources": []})["tier"] == 2


def test_answer_external_default_limit_leaves_room_for_long_answers():
    # 11-11 K-52: 18쪽 전체 번역이 8192 토큰 상한에서 잘려 실패했다
    assert server.AnswerExternalIn(masked="[[ORG_1]]", mapping={"[[ORG_1]]": "a"}).max_tokens == 16000
