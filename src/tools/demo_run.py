"""시연 문서 세트(src/data/demo/demo_docs_v1.jsonl)를 현재 파이프라인에 넣어 기대와 비교한다.

파이프라인: 탐지(규칙+30B) → 라우팅(tev1 v1) → 결정 규칙(decide.py)
정답 구간에는 tier가 있다. 1 = 항상 가림, 2 = 정책 토글(이름). 재현율은 등급별로 따로 낸다.

사용: python src/tools/demo_run.py [--no-doc]
결과: src/results/demo_run_<stamp>.md
팀 문서 초안: 프로젝트 루트 "시연 문서 세트 v1 (YYYY-MM-DD).md" (4절 '격차와 규칙 변경'은 사람이 채운 뒤 md2pdf)
"""
import argparse
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from common import RESULTS, ROOT, LABEL_KO, Span, find_all, load_samples, utf8_stdout  # noqa: E402
from decide import decide  # noqa: E402
from detect import detect  # noqa: E402
from eval import score  # noqa: E402
from route import route  # noqa: E402

DEMO = ROOT / "data" / "demo" / "demo_docs_v1.jsonl"
TIER_TABLE = [
    "| 등급 | 라벨 | 처리 | 예 |", "|---|---|---|---|",
    "| 1 | 식별번호(doc_no), 금액(price), 연락처(contact), 사업자·주민번호(biz_no), 사업명·무기체계명(project), 고객사·협력사명(company) | 항상 가림. 해제하려면 사유를 남긴다 | NCR-2026-0147, 850,000원, 010-…, KX-3 구동장치, 한빛에어로 |",
    "| 2 | 사람 이름(person). 회사 정책으로 company를 여기로 내릴 수 있다 | 탐지는 하되 가림은 정책 토글. 시연 기본값은 끔 | 김지영, 정민호 |",
    "| 3 | 직급·부서, 날짜, 수량, 치수·물성 수치, 공개 규격 번호, 재질 기호 | 가리지 않는다. 식별번호와 사업명을 가려 수치가 어느 부품의 것인지 연결을 끊는다 | 과장, 200 EA, Ra 3.2, AS9100D, 6061-T6 |",
]


def golds(r, tier=None):
    out = []
    for g in r["spans"]:
        if tier is not None and g.get("tier", 1) != tier:
            continue
        hits = find_all(r["text"], g["text"])
        if not hits:
            raise ValueError(f"{r['id']}: 정답 구간 '{g['text']}' 이(가) 본문에 없음")
        for s, e in hits:
            out.append(Span(s, e, g["text"], g["label"], ["gold"]))
    return out


def pct(s):
    return "-" if s is None else f"{s['hits']}/{s['gold']}"


def run(rows):
    out = []
    for r in rows:
        det = detect(r["text"])
        rt = route(r["text"])
        d = decide(r["text"], det["spans"], rt)
        g1, g2 = golds(r, 1), golds(r, 2)
        s1 = score(det["spans"], g1) if g1 else None
        s2 = score(det["spans"], g2) if g2 else None
        sall = score(det["spans"], golds(r))
        res = {
            "id": r["id"], "case": r["case"], "gold_route": r["route"], "tev1": rt["choice"],
            "tev1_p": max(rt["probabilities"].values()) if rt.get("probabilities") else None,
            "decide": d["action"], "reasons": d["reasons"], "warnings": d["warnings"] + det.get("warnings", []),
            "needs_approval": d["needs_approval"], "s1": s1, "s2": s2, "fp": sall["fp_texts"],
            "spans": [(sp.label, sp.text, ",".join(sp.sources)) for sp in det["spans"]],
            "llm_s": det["timing"].get("llm_total_s"), "rules_ms": det["timing"].get("rules_ms"),
        }
        out.append(res)
        ok = "O" if res["decide"] == res["gold_route"] else "X"
        print(f"{r['id']} {ok} 기대={r['route']:<8} tev1={rt['choice']:<8} 결정={d['action']:<8} "
              f"등급1 {pct(s1)} 등급2 {pct(s2)} 오탐 {len(res['fp'])} 30B {res['llm_s']}s  {'; '.join(d['reasons'])}", flush=True)
    return out


def results_md(rows, res, stamp):
    md = [f"# 시연 문서 세트 v1 · 현재 파이프라인 결과 {stamp}", "",
          "탐지 규칙+30B → tev1 v1 → 결정 규칙. 등급 1 = 항상 가림, 등급 2 = 이름(정책 토글).", "",
          "| 문서 | 경우 | 기대 경로 | tev1 | 결정 | 등급1 적중 | 등급2 적중 | 오탐 | 30B 초 |", "|---|---|---|---|---|---|---|---|---|"]
    for r, x in zip(rows, res):
        mark = "" if x["decide"] == x["gold_route"] else " ✗"
        md.append(f"| {x['id']} | {x['case']} | {x['gold_route']} | {x['tev1']} ({x['tev1_p']:.2f}) | {x['decide']}{mark} | "
                  f"{pct(x['s1'])} | {pct(x['s2'])} | {len(x['fp'])} | {x['llm_s']} |")
    md.append("")
    for x in res:
        md += [f"## {x['id']} · {x['case']}", "",
               f"- 결정: {x['decide']} (기대 {x['gold_route']}) · 승인 필요: {x['needs_approval']} · 사유: {'; '.join(x['reasons']) or '-'}",
               f"- 경고: {'; '.join(x['warnings']) or '-'}",
               f"- 탐지 구간 {len(x['spans'])}개: " + (", ".join(f"{LABEL_KO.get(l, l)}:{t}[{s}]" for l, t, s in x["spans"]) or "-"),
               f"- 놓친 등급 1: {', '.join(x['s1']['misses']) if x['s1'] and x['s1']['misses'] else '-'}",
               f"- 놓친 등급 2: {', '.join(x['s2']['misses']) if x['s2'] and x['s2']['misses'] else '-'}",
               f"- 오탐: {', '.join(x['fp']) or '-'}", ""]
    return "\n".join(md)


def team_doc(rows, res, today):
    md = [f"# 시연 문서 세트 v1 ({today})", "",
          "목적: 라우팅 결과(경로)마다 시연에 쓸 문서를 먼저 정하고, 그 문서에서 '무엇을 가리고 무엇을 막을지'를 정의한 뒤 규칙과 프롬프트를 거기에 맞춘다. "
          "문서는 방산 협력 제조 중소기업 품질팀이 실제로 다루는 형태(공지, 회의록, 부적합 보고서, 규격 점검표, 견적 비교표, 견적 회신 메일)로 썼고, 회사·사업명은 전부 가상이다.", "",
          "## 1. 설계 원칙: 탐지는 전부, 가림은 등급 정책", "",
          "탐지기는 라벨 7종을 전부 찾는다. 무엇을 실제로 가릴지는 회사 보안 담당자가 등급 정책으로 정한다. "
          "그래서 '이름은 노출돼도 되는 회사'는 등급 2를 꺼 두면 되고, 탐지 수치와 평가 세트는 그대로 유효하다.", ""] + TIER_TABLE + ["",
          "차단과 사내 강제는 결정 규칙(decide.py)이 맡는다: 통째 유출(구간 4개 이상·라벨 3종 이상 + '전부 정리·표로 취합' 요청), 사업자·주민번호 3개 이상, "
          "'대외비·외부 공유 금지·내부 공유용' 표기는 사내 강제, '가리지 마·마스킹 없이' 지시는 가림 유지 + 경고.", "",
          "## 2. 경로별 시연 문서", ""]
    for r in rows:
        t1 = [g for g in r["spans"] if g.get("tier", 1) == 1]
        t2 = [g for g in r["spans"] if g.get("tier", 1) == 2]
        md += [f"### {r['id']} · {r['case']}", "",
               f"- 문서 형태: {r['format']}", f"- 기대 경로: **{r['route']}** — {r['why']}", f"- 카드: {r['card']}",
               f"- 가릴 구간 등급 1 ({len(t1)}개): " + (", ".join(f"{g['text']}({LABEL_KO.get(g['label'], g['label'])})" for g in t1) or "없음"),
               f"- 등급 2 ({len(t2)}개, 기본 끔): " + (", ".join(g["text"] for g in t2) or "없음"), "",
               "```", r["text"], "```", ""]
    md += ["## 3. 현재 파이프라인 결과", "",
           "| 문서 | 기대 경로 | tev1 | 결정 | 등급1 적중 | 등급2 적중 | 오탐 | 30B 초 |", "|---|---|---|---|---|---|---|---|"]
    for x in res:
        mark = "" if x["decide"] == x["gold_route"] else " ✗"
        md.append(f"| {x['id']} | {x['gold_route']} | {x['tev1']} ({x['tev1_p']:.2f}) | {x['decide']}{mark} | "
                  f"{pct(x['s1'])} | {pct(x['s2'])} | {len(x['fp'])} | {x['llm_s']} |")
    md += [""]
    for x in res:
        miss1 = ", ".join(x["s1"]["misses"]) if x["s1"] and x["s1"]["misses"] else "-"
        miss2 = ", ".join(x["s2"]["misses"]) if x["s2"] and x["s2"]["misses"] else "-"
        md.append(f"- {x['id']}: 사유 {'; '.join(x['reasons']) or '-'} · 경고 {'; '.join(x['warnings']) or '-'} · 놓친 등급1 {miss1} · 놓친 등급2 {miss2} · 오탐 {', '.join(x['fp']) or '-'}")
    md += ["", "## 4. 격차와 규칙 변경", "", "(분석 추가 예정)", "",
           "## 5. 팀 결정 필요", "",
           "1. 이름(person)을 등급 2로 두고 시연 기본값을 '끔'으로 할지. 연락처와 함께 있으면 개인정보가 되므로 연락처는 등급 1 유지.",
           "2. 고객사·협력사명(company)을 등급 1에 둘지, 정책 토글로 내릴지. 방산 협력 관계 자체가 민감하다고 보면 등급 1.",
           "3. 시연 문서의 회사·사업명은 가상명 사용(실제 방산 대기업·무기체계명은 사전에만 둠).",
           "4. 치수·물성 수치는 가리지 않고 식별번호·사업명으로 연결을 끊는 원칙을 Q&A 답변으로 준비.",
           "5. 외부 응답에서 자리표를 원문으로 되돌리는 복원 기능을 1차 범위에 넣을지(백엔드 작업량).", ""]
    return "\n".join(md)


def main():
    utf8_stdout()
    ap = argparse.ArgumentParser()
    ap.add_argument("--no-doc", action="store_true", help="팀 문서 초안을 쓰지 않음")
    args = ap.parse_args()
    rows = load_samples(DEMO)
    stamp = datetime.now().strftime("%Y%m%d_%H%M")
    res = run(rows)
    out = RESULTS / f"demo_run_{stamp}.md"
    out.write_text(results_md(rows, res, stamp), encoding="utf-8")
    print("결과:", out)
    if not args.no_doc:
        today = datetime.now().strftime("%Y-%m-%d")
        doc = ROOT.parent / "docs" / f"시연 문서 세트 v1 ({today}).md"
        doc.write_text(team_doc(rows, res, today), encoding="utf-8")
        print("팀 문서 초안:", doc)


if __name__ == "__main__":
    main()
