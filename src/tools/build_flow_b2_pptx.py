"""흐름도 B 2안(⑬ 되먹임을 RAG = 결정 기록 검색으로 바꾼 안)을 한 장짜리 .pptx로 만든다.

기존 덱(흐름도 A/B/C)은 건드리지 않고 별도 파일로 저장한다. 도형·연결선은 build_flow_pptx의 헬퍼를 그대로 쓴다.

사용: python src/tools/build_flow_b2_pptx.py "출력경로.pptx"
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from pptx import Presentation  # noqa: E402
from pptx.enum.text import PP_ALIGN  # noqa: E402
from pptx.util import Inches  # noqa: E402

from build_flow_pptx import (  # noqa: E402
    C_MUTED, C_TEXT, arrow, caption, label, node, poly, text_box, title,
)


def slide_b2(prs):
    s = prs.slides.add_slide(prs.slide_layouts[6])
    title(s, "흐름도 B 2안 · 기록과 되먹임 (RAG = 결정 기록 검색)")

    # 왼쪽 열: 보안팀
    node(s, 0.6, 1.3, 3.2, 0.8, "보안팀 대시보드 (웹 호스팅)", "집계 5종 · 공격 탐지율 패널")
    node(s, 0.6, 3.3, 3.2, 0.8, "집계 API (클라우드 서버)", "SQL 집계 · 원문 없이 메타만")
    node(s, 0.6, 5.3, 3.2, 0.8, "학습 배치 (밤마다 + 즉시 스위치)", "승인 → 사전 · 해제 → 허용 목록")

    # 가운데 열: 요청 경로 · DB · 검색
    node(s, 4.6, 1.3, 4.2, 0.8, "요청 경로 A → E (흐름도 A)", "접수 · 탐지 · 라우팅 · 결정 · 가림·복원")
    node(s, 4.6, 3.3, 4.2, 0.8, "로그 DB (클라우드 서버)", "requests · spans · approvals · vectors · dict · allowlist")
    node(s, 4.6, 5.3, 4.2, 0.8, "유사 기록 검색 (요청마다)", "코사인 유사도 top-k · 과거 승인/해제 사례 k건", kind="accent")

    # 오른쪽 열: 공격 재생 · 임베딩 · 변경점
    node(s, 9.8, 1.3, 2.9, 0.8, "replay.py (팀원 PC)", "공격 세트 30건 순서대로")
    node(s, 9.8, 5.3, 2.9, 0.8, "임베딩 bge-m3 (로컬 LLM PC)", "/api/embed · 1024차원 · 지연 미측정")

    # ① replay → 요청 경로
    arrow(s, 9.8, 1.55, 8.8, 1.55)
    label(s, 8.8, 1.3, 1.0, ["POST"], align=PP_ALIGN.CENTER)

    # ⑩ 요청 경로 ↔ 로그 DB
    arrow(s, 6.7, 2.1, 6.7, 3.3, both=True)
    label(s, 6.8, 2.4, 2.4, ["⑩ 요청·구간·승인·결과·지연 ↓", "사전 · 허용 목록 ↑ (탐지가 읽음)"])

    # 집계 쿼리, ⑪ 대시보드
    arrow(s, 4.6, 3.7, 3.8, 3.7)
    label(s, 3.7, 3.42, 1.0, ["집계 쿼리"], align=PP_ALIGN.CENTER)
    arrow(s, 2.2, 3.3, 2.2, 2.1)
    label(s, 2.3, 2.55, 1.5, ["⑪ 30초마다 갱신"])

    # ⑫ 로그 DB ↔ 학습 배치
    poly(s, [(4.6, 3.95), (4.2, 3.95), (4.2, 5.7), (3.8, 5.7)], both=True)
    label(s, 4.3, 4.35, 2.3, ["⑫ 밤마다 승인·해제 기록 읽기 ↓", "사전 · 허용 목록 쓰기 ↑"])

    # ⑬a 로그 DB ↔ 유사 기록 검색
    arrow(s, 6.7, 4.1, 6.7, 5.3, both=True)
    label(s, 6.8, 4.45, 2.0, ["⑬a 벡터로 top-k 조회 ↑", "새 요청 벡터 저장 ↓"])

    # 유사 기록 검색 ↔ 임베딩
    arrow(s, 8.8, 5.9, 9.8, 5.9, both=True)
    label(s, 8.8, 6.02, 1.0, ["텍스트 → 벡터"], align=PP_ALIGN.CENTER, size=8.5)

    # ⑬ 되먹임 (RAG): 요청 텍스트 ↓ · 유사 사례 ↑ → 30B 예시 + 승인 카드
    poly(s, [(8.8, 5.5), (9.3, 5.5), (9.3, 1.95), (8.8, 1.95)], both=True, dashed=True)
    label(s, 9.4, 2.15, 3.3, ["⑬ 요청 텍스트 ↓ · 유사 사례 k건 ↑", "30B 예시(few-shot) + 카드 '비슷한 과거 사례'"])

    # 변경점 카드
    text_box(s, 9.8, 2.85, 2.95, 2.3, [
        ("1안과 달라지는 것", 10.5, True, C_TEXT),
        ("· few-shot 선택 기준이 바뀜:", 9, False, C_MUTED),
        ("  '최근 N건' → '지금 요청과 비슷한 k건'", 9, False, C_MUTED),
        ("  (검색 결과가 모델 입력으로 = RAG)", 9, False, C_MUTED),
        ("· 로그 DB에 요청 벡터(1024차원) 열 추가", 9, False, C_MUTED),
        ("· 로컬 PC에 임베딩 모델 bge-m3 하나 더 상주", 9, False, C_MUTED),
        ("  (요청마다 1회 호출, 동시 구동 지연 미측정)", 9, False, C_MUTED),
        ("· 승인 카드에 '비슷한 과거 사례' 영역 추가", 9, False, C_MUTED),
        ("· 사전·허용 목록 갱신(⑫)은 1안과 같음", 9, False, C_MUTED),
    ])

    caption(s, [
        "1안과 다른 점은 ⑬ 하나다. 되먹임이 밤마다 사전을 고치는 데서 끝나지 않고, 요청마다 비슷한 과거 승인·해제 사례를 찾아 30B 예시와 승인 카드에 넣는다.",
        "민감정보 사전 조회는 RAG가 아니라 규칙·DB 조회다. 채택 조건: 50개 세트에서 '유사 사례 투입 시 30B 재현율 변화'와 임베딩 지연을 재서 효과가 있을 때만.",
    ])
    s.notes_slide.notes_text_frame.text = (
        "RAG라고 부를 수 있는 부분은 결정 기록 검색이다. 새 요청이 오면 bge-m3로 임베딩하고, 로그 DB에 저장된 과거 요청 벡터와 코사인 유사도로 "
        "비슷한 k건을 찾아 그 요청의 승인·해제 결과를 30B 추출 프롬프트의 예시로 넣고, 승인 카드에도 '비슷한 과거 사례'로 보여 준다. "
        "기록이 수천 건 이하이므로 벡터 DB 없이 SQLite에 벡터를 저장하고 Python에서 코사인을 계산해도 밀리초 단위다. 운영 전환 시 PostgreSQL + pgvector로 교체 가능. "
        "효과를 숫자로 못 보이면 심사에서 '그래서 RAG로 뭐가 달라졌나'에 답이 없으므로, 50개 세트 측정 후 채택 여부를 정한다.")
    return s


def main(out: Path):
    prs = Presentation()
    prs.slide_width = Inches(13.333)
    prs.slide_height = Inches(7.5)
    slide_b2(prs)
    out.parent.mkdir(parents=True, exist_ok=True)
    prs.save(str(out))
    print("saved", out)


if __name__ == "__main__":
    main(Path(sys.argv[1] if len(sys.argv) > 1 else "AI 교환기 아키텍처 흐름도 B 2안.pptx"))
