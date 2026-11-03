"""밤 배치 4 (2026-10-29 밤): 30B 입력에서 규칙 구간을 자리표로 가린 M 모드 vs 현재 C 모드.

측정: 후보 40·공격 30·공격 2차 20·영어 12·사내 2차 20·시연 6 → 혼합 재현율·오탐·30B p50/p95·출력 토큰, 그리고 긴 문서(약 30k·45k자) 시간 분해.
같은 글에 C와 M을 연달아 돌려 비결정성 영향을 줄인다. 전체 파이프라인(detect)을 그대로 쓴다.

사용: python src/tools/night_run4.py [--smoke]
결과: src/results/night4_<stamp>/report.md
"""
import argparse
import json
import sys
import time
from datetime import datetime
from pathlib import Path

SRC = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SRC))
sys.path.insert(0, str(SRC / "tools"))

from common import DATA, RESULTS, Span, find_all, load_samples, percentile, utf8_stdout  # noqa: E402
from detect import detect  # noqa: E402
from eval import score, gold_spans  # noqa: E402
from night_run import EN_PARAS, KO_HEAD  # noqa: E402

utf8_stdout()
STAMP = datetime.now().strftime("%Y%m%d_%H%M")
OUT = RESULTS / f"night4_{STAMP}"
CAND = DATA / "candidates"
SETS = {
    "후보 40": CAND / "samples_clean_20261029_1449.jsonl",
    "공격 30": CAND / "attacks_clean_20261029_1449.jsonl",
    "공격 2차 20": CAND / "attacks_round2_20261029_1536.jsonl",
    "영어 12": CAND / "english_round1_20261029_1920.jsonl",
    "사내 2차 20": CAND / "local_round2_20261029_1536.jsonl",
    "시연 6": DATA / "demo" / "demo_docs_v1.jsonl",
}
MODES = ["C", "M"]
_log = None


def log(msg):
    print(msg, flush=True)
    _log.write(msg + "\n")
    _log.flush()


def f2(x):
    return "-" if x is None else f"{x:.2f}"


def pct(h, g):
    return "-" if not g else f"{h / g:.0%}"


def long_doc(target_tokens):
    base = load_samples(DATA / "samples.jsonl")
    body, gold_texts = KO_HEAD, {}
    for t in ["한국항공우주산업", "BRK-2210-07B", "PO-25-00421", "1,480,000원", "정우성", "010-8765-4321", "ws.jung@hanbit-p.co.kr", "백호 2차"]:
        gold_texts[t] = None
    i = 0
    while len(body) < target_tokens * 3:
        r = base[i % len(base)]
        body += f"\n\n[{i + 1}] " + r["text"] + "\n" + EN_PARAS[i % len(EN_PARAS)]
        for g in r["spans"]:
            gold_texts[g["text"]] = g["label"]
        i += 1
    golds = [Span(s, e, t, lab or "other", ["gold"]) for t, lab in gold_texts.items() for s, e in find_all(body, t)]
    return body, golds


def main():
    global _log
    ap = argparse.ArgumentParser()
    ap.add_argument("--smoke", action="store_true")
    args = ap.parse_args()
    OUT.mkdir(parents=True, exist_ok=True)
    _log = open(OUT / "log.txt", "a", encoding="utf-8")
    log(f"시작 {datetime.now():%Y-%m-%d %H:%M:%S} smoke={args.smoke} → {OUT}")
    agg = {m: {n: {"g": 0, "hh": 0, "fp": 0, "s": [], "tok": [], "ptok": []} for n in SETS} for m in MODES}
    diffs = []
    for n, path in SETS.items():
        rows = load_samples(path)
        rows = rows[:2] if args.smoke else rows
        for r in rows:
            golds = gold_spans(r)
            per = {}
            for m in MODES:
                d = detect(r["text"], prompt_mode=m)
                sc = score(d["spans"], golds)
                a = agg[m][n]
                a["g"] += sc["gold"]; a["hh"] += sc["hits"]; a["fp"] += sc["fp"]
                a["s"].append(d["timing"].get("llm_total_s") or 0)
                a["tok"].append(d["timing"].get("llm_eval_tokens") or 0)
                a["ptok"].append(d["timing"].get("llm_prompt_tokens") or 0)
                per[m] = (sc, d["timing"].get("llm_total_s"))
            log(f"{n} {r['id']}: " + " | ".join(f"{m} {per[m][0]['hits']}/{per[m][0]['gold']} fp{per[m][0]['fp']} {f2(per[m][1])}s" for m in MODES))
            if (per["C"][0]["hits"], per["C"][0]["fp"]) != (per["M"][0]["hits"], per["M"][0]["fp"]):
                diffs.append(f"- {n} {r['id']}: C {per['C'][0]['hits']}/{per['C'][0]['gold']} fp{per['C'][0]['fp']} → M {per['M'][0]['hits']}/{per['M'][0]['gold']} fp{per['M'][0]['fp']}"
                             f" · M 놓침 {per['M'][0]['misses'] or '-'} · M 오탐 {per['M'][0]['fp_texts'] or '-'}")
    md = [f"# 밤 배치 4 · 30B 입력 자리표 가림(M) vs 규칙 목록 제시(C) {STAMP}", "",
          "| 세트 | 모드 | 혼합 재현율 | 오탐 | 30B p50 | p95 | 출력 토큰 p50 | 입력 토큰 p50 |", "|---|---|---|---|---|---|---|---|"]
    tot = {m: {"hh": 0, "g": 0, "fp": 0, "s": [], "tok": []} for m in MODES}
    for n in SETS:
        for m in MODES:
            a = agg[m][n]
            md.append(f"| {n} | {m} | {pct(a['hh'], a['g'])} | {a['fp']} | {f2(percentile(a['s'], 50))}s | {f2(percentile(a['s'], 95))}s | "
                      f"{percentile(a['tok'], 50)} | {percentile(a['ptok'], 50)} |")
            t = tot[m]
            t["hh"] += a["hh"]; t["g"] += a["g"]; t["fp"] += a["fp"]; t["s"] += a["s"]; t["tok"] += a["tok"]
    md += ["", "총합: " + ", ".join(f"{m} 적중 {t['hh']}/{t['g']} 오탐 {t['fp']} p50 {f2(percentile(t['s'], 50))}s 출력 토큰 합 {sum(t['tok'])}" for m, t in tot.items()), "",
           "C와 M이 다른 항목:"] + (diffs or ["- 없음"]) + [""]
    log("\n".join(md[-3 - len(diffs):]))
    # 긴 문서
    md += ["## 긴 문서 시간 분해", "", "| 목표 토큰 | 글자 | 모드 | 조각 | 입력 토큰 | 출력 토큰 | 프롬프트 처리 초 | 생성 초 | 전체 초 | 재현율 | 오탐 |", "|---|---|---|---|---|---|---|---|---|---|---|"]
    for tok in ([6000] if args.smoke else [10000, 15000]):
        body, golds = long_doc(tok)
        for m in MODES:
            t0 = time.perf_counter()
            d = detect(body, prompt_mode=m)
            wall = time.perf_counter() - t0
            sc = score(d["spans"], golds)
            tm = d["timing"]
            md.append(f"| {tok} | {len(body)} | {m} | {tm.get('chunks')} | {tm.get('llm_prompt_tokens')} | {tm.get('llm_eval_tokens')} | "
                      f"{f2(tm.get('llm_prompt_eval_s'))} | {f2(tm.get('llm_eval_s'))} | {wall:.1f} | {pct(sc['hits'], sc['gold'])} ({sc['hits']}/{sc['gold']}) | {sc['fp']} |")
            log(f"긴 문서 {tok} {m}: {wall:.1f}s 재현율 {sc['hits']}/{sc['gold']} 오탐 {sc['fp']} 출력 토큰 {tm.get('llm_eval_tokens')} 경고 {d['warnings']}"
                + (f" 놓침 {sc['misses'][:5]}" if sc["misses"] else "") + (f" 오탐 {sc['fp_texts'][:5]}" if sc["fp_texts"] else ""))
    text = "\n".join(md)
    (OUT / "report.md").write_text(text, encoding="utf-8")
    (OUT / "results.json").write_text(json.dumps({"agg": agg, "diffs": diffs}, ensure_ascii=False, indent=1, default=str), encoding="utf-8")
    log(f"보고서: {OUT / 'report.md'}\n끝 {datetime.now():%Y-%m-%d %H:%M:%S}")


if __name__ == "__main__":
    main()
