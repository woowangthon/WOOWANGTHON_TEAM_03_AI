"""라우팅 검증: jsonl의 route 정답과 tev1 판정을 비교한다 (차단 갈래 포함).

사용: python src/tools/route_check.py 파일1.jsonl [파일2.jsonl ...] [--variant v1_en_capability]
결과: src/results/route_check_YYYYMMDD_HHMM.md
"""
import argparse
import sys
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from common import RESULTS, load_samples, percentile, utf8_stdout  # noqa: E402
from route import DEFAULT_VARIANT, route  # noqa: E402


def main():
    utf8_stdout()
    ap = argparse.ArgumentParser()
    ap.add_argument("files", nargs="+")
    ap.add_argument("--variant", default=DEFAULT_VARIANT)
    args = ap.parse_args()

    md = [f"# 라우팅 검증 {datetime.now():%Y-%m-%d %H:%M} · 기준 {args.variant}", ""]
    for f in args.files:
        rows = load_samples(Path(f))
        conf = defaultdict(Counter)
        secs, wrong = [], []
        for r in rows:
            res = route(r["text"], args.variant)
            secs.append(res["seconds"])
            conf[r["route"]][res["choice"]] += 1
            if res["choice"] != r["route"]:
                p = res["probabilities"]
                wrong.append(f"{r['id']}: 정답 {r['route']} → {res['choice']} (p local {p.get('local', 0):.2f} / external {p.get('external', 0):.2f} / block {p.get('block', 0):.2f})")
            print(f"{r['id']} gold={r['route']:<8} got={res['choice']:<8} {res['seconds']:.2f}s", flush=True)
        n = len(rows)
        ok = sum(conf[g][g] for g in conf)
        md += [f"## {Path(f).name} · {n}건 · 일치 {ok}/{n} ({ok / n:.0%}) · p50 {percentile(secs, 50):.2f}s", "",
               "| 정답 \\ 판정 | local | external | block |", "|---|---|---|---|"]
        for g in ["local", "external", "block"]:
            if conf[g]:
                md.append(f"| {g} | {conf[g]['local']} | {conf[g]['external']} | {conf[g]['block']} |")
        md += ["", "틀린 것:"] + ([f"- {w}" for w in wrong] or ["- 없음"]) + [""]
    text = "\n".join(md)
    print("\n" + text)
    out = RESULTS / f"route_check_{datetime.now():%Y%m%d_%H%M}_{args.variant}.md"
    out.write_text(text, encoding="utf-8")
    print("저장:", out)


if __name__ == "__main__":
    main()
