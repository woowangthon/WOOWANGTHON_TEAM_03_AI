"""전체 아키텍처 흐름도 A/B/C를 PowerPoint(.pptx)로 만든다. 도형과 연결선은 전부 네이티브라 PowerPoint에서 편집할 수 있다.

사용: python src/tools/build_flow_pptx.py "출력경로.pptx"
"""
import sys
from pathlib import Path

from lxml import etree
from pptx import Presentation
from pptx.dml.color import RGBColor
from pptx.enum.dml import MSO_LINE
from pptx.enum.shapes import MSO_CONNECTOR, MSO_SHAPE
from pptx.enum.text import MSO_ANCHOR, PP_ALIGN
from pptx.oxml.ns import qn
from pptx.util import Inches, Pt

FONT = "Malgun Gothic"
C_TEXT = RGBColor(0x1A, 0x21, 0x2C)
C_MUTED = RGBColor(0x5B, 0x68, 0x78)
C_NODE = RGBColor(0xF4, 0xF6, 0xF8)
C_NODE_LINE = RGBColor(0x8A, 0x96, 0xA6)
C_ARROW = RGBColor(0x3A, 0x45, 0x55)
C_ACCENT = RGBColor(0x17, 0x60, 0x7A)
C_ACCENT_FILL = RGBColor(0xE3, 0xEF, 0xF4)
C_WARN = RGBColor(0xA3, 0x5A, 0x0B)
C_WARN_FILL = RGBColor(0xFB, 0xEA, 0xDB)
C_ZONE = RGBColor(0x9A, 0xA5, 0xB4)
C_WHITE = RGBColor(0xFF, 0xFF, 0xFF)


def _font(run, size, bold=False, color=C_TEXT):
    run.font.name = FONT
    run.font.size = Pt(size)
    run.font.bold = bold
    run.font.color.rgb = color
    # 한글 글꼴도 같은 서체로
    rPr = run._r.get_or_add_rPr()
    ea = rPr.find(qn("a:ea"))
    if ea is None:
        ea = etree.SubElement(rPr, qn("a:ea"))
    ea.set("typeface", FONT)


def _fill_lines(tf, lines, align, anchor, margin=0.04):
    """lines: [(text, size, bold, color), ...]"""
    tf.word_wrap = True
    tf.vertical_anchor = anchor
    tf.margin_left = tf.margin_right = Inches(margin)
    tf.margin_top = tf.margin_bottom = Inches(0.02)
    for i, (text, size, bold, color) in enumerate(lines):
        p = tf.paragraphs[0] if i == 0 else tf.add_paragraph()
        p.alignment = align
        p.space_after = Pt(0)
        p.space_before = Pt(1 if i else 0)
        r = p.add_run()
        r.text = text
        _font(r, size, bold, color)


def text_box(slide, x, y, w, h, lines, align=PP_ALIGN.LEFT, anchor=MSO_ANCHOR.TOP):
    tb = slide.shapes.add_textbox(Inches(x), Inches(y), Inches(w), Inches(h))
    _fill_lines(tb.text_frame, lines, align, anchor, margin=0.0)
    return tb


def zone(slide, x, y, w, h, label, label_at="top"):
    s = slide.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, Inches(x), Inches(y), Inches(w), Inches(h))
    s.adjustments[0] = 0.04
    s.fill.background()
    s.line.color.rgb = C_ZONE
    s.line.width = Pt(1)
    s.line.dash_style = MSO_LINE.DASH
    s.shadow.inherit = False
    s.name = f"zone {label}"
    ly = y + 0.06 if label_at == "top" else y + h - 0.28
    text_box(slide, x + 0.15, ly, w - 0.3, 0.22, [(label, 10, False, C_MUTED)])
    return s


def node(slide, x, y, w, h, title, sub=None, kind="normal", title_size=12, sub_size=9.5):
    s = slide.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, Inches(x), Inches(y), Inches(w), Inches(h))
    s.adjustments[0] = 0.12
    s.shadow.inherit = False
    s.name = f"node {title}"
    s.fill.solid()
    if kind == "accent":
        s.fill.fore_color.rgb = C_ACCENT_FILL
        s.line.color.rgb = C_ACCENT
        s.line.width = Pt(1.5)
    elif kind == "warn":
        s.fill.fore_color.rgb = C_WARN_FILL
        s.line.color.rgb = C_WARN
        s.line.width = Pt(1.5)
    else:
        s.fill.fore_color.rgb = C_NODE
        s.line.color.rgb = C_NODE_LINE
        s.line.width = Pt(1)
    lines = [(title, title_size, True, C_TEXT)]
    if sub:
        lines.append((sub, sub_size, False, C_MUTED))
    _fill_lines(s.text_frame, lines, PP_ALIGN.CENTER, MSO_ANCHOR.MIDDLE)
    return s


def _arrowheads(conn, head=False, tail=True):
    ln = conn.line._get_or_add_ln()
    if head:
        e = etree.SubElement(ln, qn("a:headEnd"))
        e.set("type", "triangle"); e.set("w", "med"); e.set("len", "med")
    if tail:
        e = etree.SubElement(ln, qn("a:tailEnd"))
        e.set("type", "triangle"); e.set("w", "med"); e.set("len", "med")


def segment(slide, x1, y1, x2, y2, dashed=False, color=C_ARROW, width=1.5):
    c = slide.shapes.add_connector(MSO_CONNECTOR.STRAIGHT, Inches(x1), Inches(y1), Inches(x2), Inches(y2))
    c.line.color.rgb = color
    c.line.width = Pt(width)
    if dashed:
        c.line.dash_style = MSO_LINE.DASH
    return c


def arrow(slide, x1, y1, x2, y2, both=False, dashed=False):
    c = segment(slide, x1, y1, x2, y2, dashed)
    _arrowheads(c, head=both, tail=True)
    return c


def poly(slide, pts, both=False, dashed=False):
    segs = []
    for (ax, ay), (bx, by) in zip(pts, pts[1:]):
        segs.append(segment(slide, ax, ay, bx, by, dashed))
    _arrowheads(segs[-1], head=False, tail=True)
    if both:
        _arrowheads(segs[0], head=True, tail=False)
    return segs


def label(slide, x, y, w, lines, align=PP_ALIGN.LEFT, size=9):
    h = 0.19 * len(lines) + 0.02
    return text_box(slide, x, y, w, h, [(t, size, False, C_TEXT if i == 0 else C_MUTED) for i, t in enumerate(lines)], align=align)


def title(slide, text, eyebrow="AI 교환기 전체 아키텍처"):
    text_box(slide, 0.5, 0.22, 12.3, 0.22, [(eyebrow, 10, False, C_ACCENT)])
    text_box(slide, 0.5, 0.42, 12.3, 0.55, [(text, 24, True, C_TEXT)])


def caption(slide, lines):
    """줄바꿈 위치를 통제하려고 줄 단위로 받는다 (한글은 단어 중간에서도 꺾이므로)."""
    if isinstance(lines, str):
        lines = [lines]
    text_box(slide, 0.5, 6.85, 12.33, 0.5, [(t, 10.5, False, C_MUTED) for t in lines])


def slide_a(prs):
    s = prs.slides.add_slide(prs.slide_layouts[6])
    title(s, "흐름도 A · 요청이 지나가는 길")
    zone(s, 0.5, 1.0, 12.33, 1.15, "브라우저 (Vercel)")
    zone(s, 0.5, 2.35, 12.33, 1.5, "Oracle 무료 VM · 게이트웨이 FastAPI + SQLite", label_at="bottom")
    zone(s, 0.5, 4.3, 9.45, 2.4, "집 PC · Ollama")
    zone(s, 10.2, 4.3, 2.63, 2.4, "외부 LLM API")

    node(s, 0.9, 1.3, 4.8, 0.7, "직원 화면", "입력 → 하이라이트 → 승인 카드 → 답변 + 배지")
    node(s, 0.9, 2.75, 1.9, 0.75, "접수 /requests", "POST · 요청 저장 · 대기")
    node(s, 3.1, 2.75, 2.1, 0.75, "탐지", "규칙·사전 즉시 + 30B 구간")
    node(s, 5.5, 2.75, 1.9, 0.75, "라우팅", "tev1 choice 1문항")
    node(s, 7.7, 2.75, 2.2, 0.75, "결정 · 승인 큐", "카드 · 로컬 · 차단 분기 (사람 결정)", kind="accent")
    node(s, 10.2, 2.75, 2.3, 0.75, "가림 · 복원", "토큰 맵 [라벨_n]")
    node(s, 3.1, 5.0, 2.1, 0.75, "30B 구간 추출", "/api/chat · JSON 스키마")
    node(s, 5.5, 5.0, 1.9, 0.75, "tev1 0.8B 라우팅", "/v1/systemone · CPU")
    node(s, 7.7, 5.0, 2.2, 0.75, "30B 로컬 답변", "외부 미전송")
    node(s, 10.35, 5.0, 2.3, 0.75, "외부 LLM", "가린 텍스트만 수신")
    text_box(s, 0.9, 5.92, 8.9, 0.75, [
        ("Qwen3 30B-A3B q4_K_M: GPU 32% / CPU 68%, 초당 39~42토큰 · tev1 0.8B: CPU 전용 · 둘이 동시 상주", 9.5, False, C_MUTED),
        ("밖에서는 Cloudflare Named Tunnel + API 키를 거쳐서만 접근 · 모든 호출은 127.0.0.1 또는 터널 주소", 9.5, False, C_MUTED),
        ("num_ctx 4096, keep_alive 30분으로 고정 (값이 바뀌면 30B가 14초 동안 다시 로드)", 9.5, False, C_MUTED),
    ])

    arrow(s, 1.6, 2.0, 1.6, 2.75)
    label(s, 1.7, 2.17, 0.75, ["① 텍스트"])
    arrow(s, 2.5, 2.75, 2.5, 2.0, dashed=True)
    label(s, 2.6, 2.17, 1.85, ["폴링 2초: 하이라이트·카드·답변"])
    arrow(s, 2.8, 3.125, 3.1, 3.125)
    label(s, 2.8, 2.9, 0.3, ["②"], align=PP_ALIGN.CENTER)
    arrow(s, 4.15, 3.5, 4.15, 5.0, both=True)
    label(s, 4.25, 3.92, 1.9, ["③ 구간 JSON", "0.7 ~ 3.7초"])
    arrow(s, 5.2, 3.125, 5.5, 3.125)
    label(s, 5.2, 2.9, 0.3, ["④"], align=PP_ALIGN.CENTER)
    arrow(s, 6.45, 3.5, 6.45, 5.0, both=True)
    label(s, 6.55, 3.92, 2.2, ["⑤ local / external / block", "0.5 ~ 0.9초"])
    arrow(s, 7.4, 3.125, 7.7, 3.125)
    label(s, 7.4, 2.9, 0.3, ["⑥"], align=PP_ALIGN.CENTER)
    arrow(s, 8.8, 3.5, 8.8, 5.0, both=True)
    label(s, 8.9, 3.92, 1.6, ["⑥b local이면 답변 생성", "외부로 안 나감"])
    poly(s, [(9.4, 2.75), (9.4, 2.25), (4.5, 2.25), (4.5, 2.0)], both=True)
    label(s, 4.6, 2.38, 4.6, ["⑦ 승인 카드 ↑ · 승인/해제 ↓ POST /approve"])
    arrow(s, 9.9, 3.125, 10.2, 3.125)
    label(s, 9.9, 2.9, 0.3, ["⑧"], align=PP_ALIGN.CENTER)
    arrow(s, 11.5, 3.5, 11.5, 5.0, both=True)
    label(s, 11.6, 3.92, 1.2, ["⑨ 가린 텍스트 ↓", "답변 ↑ 복원"])

    caption(s, [
        "요청은 VM 안에서 접수 → 탐지 → 라우팅 → 결정 → 가림·복원 순으로 흐른다. 색칠한 노드가 사람이 결정하는 자리다.",
        "외부 LLM에는 가린 텍스트만 간다. 결과와 구간은 로그 DB에 쌓인다 (흐름도 B).",
    ])
    s.notes_slide.notes_text_frame.text = (
        "직원이 텍스트를 붙여 넣으면 접수 단계가 저장하고 규칙 탐지를 즉시 돌려 1차 하이라이트를 준다. "
        "동시에 집 PC의 30B가 비정형 구간을 JSON으로 뽑고(2차 하이라이트), tev1이 local/external/block을 정한다. "
        "결정 단계는 구간 유무와 라우팅을 조합해 승인 카드, 로컬 답변, 차단 중 하나로 보낸다. "
        "직원이 승인하면 구간을 자리표시자로 바꿔 외부 LLM에 보내고, 답변의 자리표시자를 원래 값으로 복원한다.")
    return s


def slide_b(prs):
    s = prs.slides.add_slide(prs.slide_layouts[6])
    title(s, "흐름도 B · 기록과 되먹임")
    node(s, 2.6, 1.3, 4.2, 0.8, "요청 경로 A → E (흐름도 A)", "접수 · 탐지 · 라우팅 · 결정 · 가림·복원")
    node(s, 7.4, 1.3, 2.1, 0.8, "replay.py (팀원 PC)", "공격 세트 30건 순서대로")
    node(s, 10.0, 1.3, 2.8, 0.8, "보안팀 대시보드 (Vercel)", "집계 5종 · 공격 탐지율 패널")
    node(s, 2.6, 3.3, 4.2, 0.8, "로그 DB (SQLite, VM)", "requests · spans · approvals · attack_runs")
    node(s, 10.0, 3.3, 2.8, 0.8, "집계 /stats (VM)", "SQL 집계 · 원문 없이 메타만")
    node(s, 2.6, 5.3, 4.2, 0.8, "학습 배치 (VM, 밤마다 + 즉시 스위치)", "승인 → 사전 · 해제 → 허용 목록 · 최근 N건 few-shot")

    arrow(s, 7.4, 1.7, 6.8, 1.7)
    label(s, 6.8, 1.44, 0.6, ["POST"], align=PP_ALIGN.CENTER)
    arrow(s, 4.7, 2.1, 4.7, 3.3)
    label(s, 4.85, 2.55, 3.6, ["⑩ 요청 · 구간 · 승인 · 결과 · 지연 기록"])
    arrow(s, 6.8, 3.7, 10.0, 3.7)
    label(s, 7.0, 3.42, 3.0, ["집계 쿼리"], align=PP_ALIGN.CENTER)
    arrow(s, 11.4, 3.3, 11.4, 2.1)
    label(s, 11.55, 2.55, 1.6, ["⑪ 30초마다 갱신"])
    arrow(s, 4.7, 4.1, 4.7, 5.3)
    label(s, 4.85, 4.55, 3.6, ["⑫ 밤마다 승인·해제 기록 읽기"])
    poly(s, [(2.6, 5.7), (1.6, 5.7), (1.6, 1.7), (2.6, 1.7)], dashed=True)
    label(s, 0.3, 3.25, 1.2, ["⑬ 사전 추가", "허용 목록", "few-shot 갱신"], align=PP_ALIGN.RIGHT)

    caption(s, [
        "모든 요청·구간·승인·결과는 로그 DB 한 곳에 쌓인다. 대시보드는 집계 API를 30초마다 읽고, 공격 세트는 재생 스크립트가 같은 접수 API로 흘려 넣는다.",
        "학습 배치는 승인·해제 기록으로 사전과 few-shot을 고쳐 다음 탐지에 반영한다.",
    ])
    s.notes_slide.notes_text_frame.text = (
        "요청 테이블에는 경로, 민감 여부, 구간 수, 가린 수, 상태, 단계별 지연, 모델 버전이 들어간다. "
        "집계 API는 원문을 내보내지 않는다. 공격 세트 재생은 탐지율이 올라가는 장면을 만들어 시연이 '막았다'로만 보이지 않게 한다. "
        "학습 배치는 승인된 구간을 사전에, 해제된 구간을 허용 목록에 넣고 최근 기록을 30B few-shot으로 쓴다.")
    return s


def slide_c(prs):
    s = prs.slides.add_slide(prs.slide_layouts[6])
    title(s, "흐름도 C · 폴백")
    node(s, 0.9, 1.8, 3.4, 1.1, "헬스체크 (VM, 5분마다)", "터널 → 집 PC Ollama 응답 확인")
    node(s, 5.0, 1.8, 3.4, 1.1, "정상: 집 PC 30B · tev1 사용", "흐름도 A 그대로")
    node(s, 9.0, 1.8, 3.8, 1.1, "실패: VM qwen3 4B (CPU) 폴백", "규칙 탐지 + 4B 답변 · 화면에 \"간단 모드\" 표시", kind="warn")
    arrow(s, 4.3, 2.35, 5.0, 2.35)
    label(s, 4.3, 2.07, 0.7, ["응답 OK"], align=PP_ALIGN.CENTER)
    poly(s, [(2.6, 2.9), (2.6, 3.8), (10.9, 3.8), (10.9, 2.9)])
    label(s, 3.0, 3.9, 7.5, ["응답 없음 · 타임아웃 → 폴백 플래그 켬 (복구되면 다음 헬스체크에서 자동 복귀)"], align=PP_ALIGN.CENTER, size=10)

    text_box(s, 0.9, 4.65, 8.0, 0.25, [("간단 모드에서 달라지는 것", 11, True, C_TEXT)])
    node(s, 0.9, 5.0, 3.4, 1.0, "탐지", "규칙·사전만 돌리고 30B 추출은 생략", title_size=11.5)
    node(s, 5.0, 5.0, 3.4, 1.0, "답변", "VM에 설치한 qwen3 4B가 CPU로 생성", title_size=11.5)
    node(s, 9.0, 5.0, 3.8, 1.0, "화면 · 로그", "\"간단 모드\" 배지 · 응답에 simple_mode 기록", title_size=11.5)

    caption(s, "집 PC가 꺼지거나 터널이 끊겨도 서비스는 멈추지 않는다. 품질이 떨어지는 것을 숨기지 않고 \"간단 모드\"로 표시한다. 11-13 재부팅 리허설로 전환과 복귀를 확인한다.")
    s.notes_slide.notes_text_frame.text = (
        "제출일 11-15부터 심사 종료 11-21까지 배포 URL이 살아 있어야 한다. 집 PC 절전 해제, Ollama 자동 시작, cloudflared 서비스, VM systemd 재시작을 미리 설정한다.")
    return s


def main(out: Path):
    prs = Presentation()
    prs.slide_width = Inches(13.333)
    prs.slide_height = Inches(7.5)
    slide_a(prs)
    slide_b(prs)
    slide_c(prs)
    out.parent.mkdir(parents=True, exist_ok=True)
    prs.save(str(out))
    print("saved", out)


if __name__ == "__main__":
    main(Path(sys.argv[1] if len(sys.argv) > 1 else "AI 교환기 아키텍처 흐름도.pptx"))
