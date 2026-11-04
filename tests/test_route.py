"""경로 판정(route.py): tev1 입력 길이 제한. tev1 호출은 가짜로 바꿔 실제로 보낸 state만 확인한다 (Ollama 불필요)."""
import route as route_mod
from route import ROUTE_MAX_CHARS, route, route_state

NOTICE_MAX = 40  # "…(이하 생략, 전체 N자)" 꼬리 길이 여유


def test_short_text_is_sent_as_is():
    assert route_state("아래 공지 맞춤법만 고쳐 줘.") == "아래 공지 맞춤법만 고쳐 줘."


def test_long_text_is_cut_at_a_line_end_with_a_notice():
    text = "아래 보고서를 영문으로 번역해 주세요.\n\n" + "\n".join(f"{i:04d} 줄 내용입니다." for i in range(1500))
    state = route_state(text)
    assert len(state) <= ROUTE_MAX_CHARS + NOTICE_MAX
    assert state.startswith("아래 보고서를 영문으로 번역해 주세요.")
    assert state.endswith(f"…(이하 생략, 전체 {len(text):,}자)")
    assert state.split("\n…(")[0].endswith("줄 내용입니다.")  # 줄 중간이 아니라 줄 끝에서 끊었다


def test_text_without_newlines_is_cut_at_the_limit():
    state = route_state("x" * (ROUTE_MAX_CHARS * 3))
    assert state.startswith("x" * ROUTE_MAX_CHARS) and len(state) <= ROUTE_MAX_CHARS + NOTICE_MAX


def test_route_sends_capped_state_and_reports_it(monkeypatch):
    sent = {}

    def fake_post(path, body, timeout=0):
        sent.clear()
        sent.update(body)
        return ({"answers": {"route": {"choice": "external", "probabilities": {"local": 0.2, "external": 0.7, "block": 0.1},
                                       "confidence": 0.5}}, "usage": {"input_tokens": 3000}}, 0.01)

    monkeypatch.setattr(route_mod, "post_json", fake_post)
    r = route("번역해 주세요.\n" + "본문 " * (ROUTE_MAX_CHARS))
    assert len(sent["state"]) <= ROUTE_MAX_CHARS + NOTICE_MAX
    assert r["truncated"] is True and r["state_chars"] == len(sent["state"]) and r["choice"] == "external"
    r2 = route("짧은 요청")
    assert r2["truncated"] is False and r2["state_chars"] == len("짧은 요청") and sent["state"] == "짧은 요청"
