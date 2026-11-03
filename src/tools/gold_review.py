"""정답 검토용 불일치 목록 (2026-10-30).

평가 세트를 혼합 탐지기(규칙+사전+NER+30B, 프롬프트 C)로 돌려 정답과 다른 곳만 모은다.
- 오탐 후보: 탐지기가 잡았는데 정답에 없는 구간 → 정답 누락인지, 탐지기 오탐인지 사람이 판정
- 놓침: 정답에 있는데 탐지기가 못 잡은 구간 → 정답이 맞는지(수량·규격이면 정답에서 삭제) 판정
- 표기·라벨 차이: 적중했지만 글자 범위나 라벨이 다른 것

사용: python src/tools/gold_review.py [--sets "후보 40,공격 30"] [--limit N]
결과: src/results/gold_review_<stamp>/disagreements.md, disagreements.json, summary.md
"""
import argparse
import json
import os
import sys
import time
from datetime import datetime
from pathlib import Path

SRC = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SRC))
os.environ.setdefault("HF_HUB_DISABLE_SYMLINKS_WARNING", "1")

from common import DATA, RESULTS, load_samples, utf8_stdout  # noqa: E402
from detect import detect  # noqa: E402
from eval import gold_spans, score  # noqa: E402

utf8_stdout()
CAND = DATA / "candidates"
SETS = {
    "후보 40": CAND / "samples_clean_20261029_1449.jsonl",
    "공격 30": CAND / "attacks_clean_20261029_1449.jsonl",
    "공격 2차 20": CAND / "attacks_round2_20261029_1536.jsonl",
    "사내 2차 20": CAND / "local_round2_20261029_1536.jsonl",
    "영어 12": CAND / "english_round1_20261029_1920.jsonl",
    "시연 6": DATA / "demo" / "demo_docs_v1.jsonl",
}
WINDOW = 90


def excerpt(text, start, end):
    """구간 주변만 보여주되 구간은 【 】로 표시. 짧은 본문은 통째로."""
    if len(text) <= 420:
        s, e, pre, post = 0, len(text), "", ""
    else:
        s = max(0, start - WINDOW)
        e = min(len(text), end + WINDOW)
        pre = "…" if s > 0 else ""
        post = "…" if e < len(text) else ""
    body = text[s:start] + "【" + text[start:end] + "】" + text[end:e]
    return (pre + body + post).replace("\n", " ⏎ ")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--sets", default=",".join(SETS))
    ap.add_argument("--limit", type=int, default=0)
    a = ap.parse_args()
    stamp = datetime.now().strftime("%Y%m%d_%H%M")
    out = RESULTS / f"gold_review_{stamp}"
    out.mkdir(parents=True, exist_ok=True)

    items = []
    stats = []
    t_all = time.perf_counter()
    for name in [s.strip() for s in a.sets.split(",") if s.strip()]:
        rows = load_samples(SETS[name])
        if a.limit:
            rows = rows[: a.limit]
        n_fp = n_miss = n_diff = n_gold = n_hit = 0
        t0 = time.perf_counter()
        for smp in rows:
            text = smp["text"]
            golds = gold_spans(smp)
            res = detect(text)
            preds = res["spans"]
            sc = score(preds, golds)
            n_gold += sc["gold"]
            n_hit += sc["hits"]
            # 오탐 후보 (정답과 겹치지 않는 예측)
            matched = set()
            for g in golds:
                for i, p in enumerate(preds):
                    if p.overlap(g) > 0:
                        matched.add(i)
            for i, p in enumerate(preds):
                if i in matched:
                    continue
                n_fp += 1
                items.append({
                    "set": name, "id": smp["id"], "type": "오탐 후보",
                    "text": p.text, "label": p.label, "start": p.start, "end": p.end,
                    "sources": list(p.sources), "excerpt": excerpt(text, p.start, p.end),
                    "note": smp.get("note", ""), "verdict": "",
                })
            # 놓침 (50% 이상 덮는 예측 없음)
            for g in golds:
                best = max((p.overlap(g) for p in preds), default=0)
                glen = g.end - g.start
                if best < 0.5 * glen:
                    n_miss += 1
                    items.append({
                        "set": name, "id": smp["id"], "type": "놓침",
                        "text": g.text, "label": g.label, "start": g.start, "end": g.end,
                        "sources": ["gold"], "excerpt": excerpt(text, g.start, g.end),
                        "note": smp.get("note", ""), "verdict": "",
                    })
                else:
                    # 표기·라벨 차이
                    cand = [p for p in preds if p.overlap(g) >= 0.5 * glen]
                    p = max(cand, key=lambda q: q.overlap(g))
                    if p.text != g.text or p.label != g.label:
                        n_diff += 1
                        items.append({
                            "set": name, "id": smp["id"], "type": "표기·라벨 차이",
                            "text": g.text, "label": g.label, "start": g.start, "end": g.end,
                            "pred_text": p.text, "pred_label": p.label, "sources": list(p.sources),
                            "excerpt": excerpt(text, g.start, g.end),
                            "note": smp.get("note", ""), "verdict": "",
                        })
            print(f"{name} {smp['id']}: 정답 {sc['gold']} 적중 {sc['hits']} 오탐 {sc['fp']}  {res['timing'].get('llm_total_s', 0):.1f}s", flush=True)
        stats.append({"set": name, "n": len(rows), "gold": n_gold, "hits": n_hit, "fp": n_fp, "miss": n_miss, "diff": n_diff,
                      "s": round(time.perf_counter() - t0)})

    (out / "disagreements.json").write_text(json.dumps(items, ensure_ascii=False, indent=1), encoding="utf-8")

    md = [f"# 정답 검토 불일치 목록 {stamp}", "",
          "혼합 탐지기(규칙+사전+NER+30B, 프롬프트 C)와 정답이 다른 곳만 모았다. 판정 칸에 '정답 추가' / '정답 삭제' / '라벨 교정' / '탐지기 오탐' 중 하나를 적는다.", "",
          "| 세트 | 건수 | 정답 구간 | 적중 | 재현율 | 오탐 후보 | 놓침 | 표기·라벨 차이 | 소요 |", "|---|---|---|---|---|---|---|---|---|"]
    for s in stats:
        rec = f"{s['hits'] / s['gold']:.0%}" if s["gold"] else "-"
        md.append(f"| {s['set']} | {s['n']} | {s['gold']} | {s['hits']} | {rec} | {s['fp']} | {s['miss']} | {s['diff']} | {s['s']}s |")
    md.append(f"\n총 {len(items)}건, {time.perf_counter() - t_all:.0f}s\n")
    cur = None
    for k, it in enumerate(items, 1):
        if it["set"] != cur:
            cur = it["set"]
            md.append(f"\n## {cur}\n")
        head = f"### {k}. {it['id']} · {it['type']} · `{it['text']}` ({it['label']})"
        if it["type"] == "표기·라벨 차이":
            head += f" ↔ 탐지 `{it['pred_text']}` ({it['pred_label']})"
        md.append(head)
        md.append(f"- 출처: {', '.join(it['sources'])}")
        md.append(f"- 본문: {it['excerpt']}")
        if it.get("note"):
            md.append(f"- note: {it['note']}")
        md.append("- 판정: ")
        md.append("")
    (out / "disagreements.md").write_text("\n".join(md), encoding="utf-8")
    print(f"\n저장: {out}  총 {len(items)}건  {time.perf_counter() - t_all:.0f}s")


if __name__ == "__main__":
    main()
