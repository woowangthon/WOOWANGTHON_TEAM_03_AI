"""외부 호출 모듈 (answer_external.py)의 API 호출 없는 부분: 전송 직전 유출 검사, 비용 추정."""
from answer_external import PRICES, estimate_cost, leak_check


def test_leak_check_finds_original_values_left_in_masked_text():
    mapping = {"[[ORG_1]]": "한빛에어로", "[[AMT_1]]": "850,000원"}
    assert leak_check("고객사 [[ORG_1]] 단가 [[AMT_1]]", mapping) == []
    assert leak_check("고객사 [[ORG_1]] 단가 850,000원", mapping) == ["850,000원"]


def test_estimate_cost_uses_price_table():
    usage = {"input_tokens": 1_000_000, "output_tokens": 100_000, "cache_read": 0}
    assert estimate_cost("claude-sonnet-5-5", usage) == 3.0
    assert estimate_cost("unknown-model", usage) is None
    assert {"claude-sonnet-5-5", "claude-opus-5-5"} <= set(PRICES)
