"""탐지기 평가: 샘플을 돌려 구간 재현율, 오탐, 민감 판정 정확도, 지연을 표로 낸다.

사용: python src/eval.py [--samples 경로] [--limit N] [--no-llm]
규칙만 / 30B만 / 혼합 세 가지를 같은 실행에서 비교한다 (30B 호출은 샘플당 1회).
결과: src/results/eval_YYYYMMDD_HHMM.md 와 .json
"""
import argparse
import json
import sys
import time
from datetime import datetime

from common import DATA, RESULTS, Span, load_samples, find_all, percentile, utf8_stdout
from detect import detect, merge_spans


def gold_spans(sample):
    text = sample["text"]
    out = []
    for g in sample.get("spans", []):
        hits = find_all(text, g["text"])
        if not hits:
            raise ValueError(f"{sample['id']}: 정답 구간 '{g['text']}' 이(가) 본문에 없음")
        for s, e in hits:
            out.append(Span(s, e, g["text"], g["label"], ["gold"]))
    return out


def score(preds, golds):
    """구간 단위 채점. 정답 구간의 50% 이상을 덮는 예측이 있으면 적중."""
    matched_pred = set()
    hits = exact = label_ok = 0
    misses = []
    for g in golds:
        best = None
        glen = g.end - g.start
        for i, p in enumerate(preds):
            ov = p.overlap(g)
            if ov > 0:
                matched_pred.add(i)
            if ov >= 0.5 * glen and (best is None or ov > best[0]):
                best = (ov, i)
        if best is None:
            misses.append(f"{g.text}({g.label})")
        else:
            hits += 1
            p = preds[best[1]]
            exact += int(p.text == g.text)
            label_ok += int(p.label == g.label)
    fps = [p for i, p in enumerate(preds) if i not in matched_pred]
    return {
        "gold": len(golds), "hits": hits, "exact": exact, "label_ok": label_ok,
        "pred": len(preds), "fp": len(fps),
        "misses": misses, "fp_texts": [f"{p.text}({p.label})" for p in fps],
    }


def summarize(rows, key):
    g = sum(r[key]["gold"] for r in rows)
    h = sum(r[key]["hits"] for r in rows)
    ex = sum(r[key]["exact"] for r in rows)
    lo = sum(r[key]["label_ok"] for r in rows)
    p = sum(r[key]["pred"] for r in rows)
    fp = sum(r[key]["fp"] for r in rows)
    sens_ok = sum(1 for r in rows if (r[key]["pred"] > 0) == (r[key]["gold"] > 0))
    return {
        "recall": h / g if g else None,
        "exact_recall": ex / g if g else None,
        "label_acc": lo / h if h else None,
        "precision": (p - fp) / p if p else None,
        "fp": fp, "pred": p, "gold": g, "hits": h,
        "sensitive_acc": sens_ok / len(rows) if rows else None,
    }


def pct(x):
    return "-" if x is None else f"{x * 100:.0f}%"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--samples", default=str(DATA / "samples.jsonl"))
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--no-llm", action="store_true", help="규칙만 평가 (30B 호출 없음)")
    ap.add_argument("--tag", default="", help="결과 파일 이름에 붙일 꼬리표 (같은 분에 두 번 돌릴 때 구분)")
    args = ap.parse_args()

    samples = load_samples(args.samples)
    if args.limit:
        samples = samples[: args.limit]
    use_llm = not args.no_llm

    rows = []
    for s in samples:
        golds = gold_spans(s)
        r = detect(s["text"], use_rules=True, use_llm=use_llm)
        row = {
            "id": s["id"], "category": s["category"], "route": s["route"],
            "timing": r["timing"], "dropped": r["dropped"],
            "rules": score(r["rule_spans"], golds),
            "hybrid": score(r["spans"], golds),
            "pred_spans": [sp.to_dict() for sp in r["spans"]],
        }
        if use_llm:
            row["llm"] = score(merge_spans(r["llm_spans"]), golds)
        rows.append(row)
        t = r["timing"]
        print(f"{s['id']} {s['category']:<9} gold {row['hybrid']['gold']:>2}  "
              f"hybrid hit {row['hybrid']['hits']:>2} fp {row['hybrid']['fp']:>2}  "
              f"rules {t.get('rules_ms', 0):.1f}ms  llm {t.get('llm_total_s', 0):.2f}s"
              + (f"  miss: {', '.join(row['hybrid']['misses'])}" if row['hybrid']['misses'] else "")
              + (f"  extra: {', '.join(row['hybrid']['fp_texts'])}" if row['hybrid']['fp_texts'] else "")
              + (f"  dropped: {[d['text'] for d in r['dropped']]}" if r['dropped'] else ""),
              flush=True)

    modes = ["rules"] + (["llm", "hybrid"] if use_llm else ["hybrid"])
    summary = {m: summarize(rows, m) for m in modes}
    llm_times = [r["timing"]["llm_total_s"] for r in rows if "llm_total_s" in r["timing"]]
    rule_times = [r["timing"]["rules_ms"] for r in rows]
    latency = {
        "rules_ms_p50": percentile(rule_times, 50), "rules_ms_p95": percentile(rule_times, 95),
        "llm_s_p50": percentile(llm_times, 50), "llm_s_p95": percentile(llm_times, 95),
        "llm_s_max": max(llm_times) if llm_times else None,
    }

    stamp = datetime.now().strftime("%Y%m%d_%H%M") + (f"_{args.tag}" if args.tag else "")
    RESULTS.mkdir(exist_ok=True)
    md = []
    md.append(f"# 탐지기 평가 {stamp}  (샘플 {len(rows)}개, 정답 구간 {summary['hybrid']['gold']}개)\n")
    md.append("| 모드 | 구간 재현율 | 정확 일치 | 라벨 일치 | 정밀도 | 오탐 수 | 민감 판정 정확도 |")
    md.append("|---|---|---|---|---|---|---|")
    name_ko = {"rules": "규칙·사전만", "llm": "30B만", "hybrid": "혼합"}
    for m in modes:
        v = summary[m]
        md.append(f"| {name_ko[m]} | {pct(v['recall'])} ({v['hits']}/{v['gold']}) | {pct(v['exact_recall'])} | "
                  f"{pct(v['label_acc'])} | {pct(v['precision'])} | {v['fp']} | {pct(v['sensitive_acc'])} |")
    md.append("")
    md.append("| 지연 | p50 | p95 | max |")
    md.append("|---|---|---|---|")
    md.append(f"| 규칙 (ms) | {latency['rules_ms_p50']:.2f} | {latency['rules_ms_p95']:.2f} | - |")
    if llm_times:
        md.append(f"| 30B 추출 (s) | {latency['llm_s_p50']:.2f} | {latency['llm_s_p95']:.2f} | {latency['llm_s_max']:.2f} |")
    md.append("")
    md.append("| 샘플 | 유형 | 정답 | 혼합 적중 | 오탐 | 놓친 구간 | 오탐 구간 | 30B 버림(환각) | 30B 초 |")
    md.append("|---|---|---|---|---|---|---|---|---|")
    for r in rows:
        h = r["hybrid"]
        md.append(f"| {r['id']} | {r['category']} | {h['gold']} | {h['hits']} | {h['fp']} | "
                  f"{', '.join(h['misses']) or '-'} | {', '.join(h['fp_texts']) or '-'} | "
                  f"{', '.join(d['text'] for d in r['dropped']) or '-'} | {r['timing'].get('llm_total_s', '-')} |")
    md.append("")
    md.append("채점: 정답 구간의 50% 이상을 덮는 예측이 있으면 적중. 정밀도 = 정답과 겹치는 예측 / 전체 예측. "
              "민감 판정 = 구간 1개 이상이면 민감으로 보고 정답 구간 유무와 비교.")
    text = "\n".join(md)
    print("\n" + text)
    (RESULTS / f"eval_{stamp}.md").write_text(text, encoding="utf-8")
    with open(RESULTS / f"eval_{stamp}.json", "w", encoding="utf-8") as f:
        json.dump({"summary": summary, "latency": latency, "rows": rows}, f, ensure_ascii=False, indent=1)
    print(f"\n저장: {RESULTS / f'eval_{stamp}.md'}")


if __name__ == "__main__":
    utf8_stdout()
    main()
