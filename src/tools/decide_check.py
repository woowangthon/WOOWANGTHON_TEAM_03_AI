"""결정 단계 검증: 탐지(규칙+30B) → 라우팅(tev1) → decide() 규칙을 세트에 돌려 정답 경로와 비교한다.

사용: python src/tools/decide_check.py 파일1.jsonl [파일2 ...] [--no-llm]
결과: src/results/decide_check_YYYYMMDD_HHMM.md
"""
import argparse
import sys
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from common import RESULTS, load_samples, utf8_stdout  # noqa: E402
from decide import decide  # noqa: E402
from detect import detect  # noqa: E402
from route import route  # noqa: E402


def main():
    utf8_stdout()
    ap = argparse.ArgumentParser()
    ap.add_argument("files", nargs="+")
    ap.add_argument("--no-llm", action="store_true")
    args = ap.parse_args()
    md = [f"# 결정 단계 검증 {datetime.now():%Y-%m-%d %H:%M} · 탐지 {'규칙만' if args.no_llm else '규칙+30B'} → tev1 v1 → 규칙(decide.py)", ""]
    for f in args.files:
        rows = load_samples(Path(f))
        conf_rule, conf_tev = defaultdict(Counter), defaultdict(Counter)
        mism, warn_ids, internal_n = [], [], 0
        for r in rows:
            det = detect(r["text"], use_llm=not args.no_llm)
            rt = route(r["text"])
            d = decide(r["text"], det["spans"], rt)
            gold = r["route"]
            conf_rule[gold][d["action"]] += 1
            conf_tev[gold][rt["choice"]] += 1
            if d["warnings"]:
                warn_ids.append(r["id"])
            if any(x.startswith("내부 전용") for x in d["reasons"]):
                internal_n += 1
            if d["action"] != gold:
                mism.append(f"{r['id']}: 정답 {gold} → {d['action']} ({'; '.join(d['reasons'])})")
            print(f"{r['id']} gold={gold:<8} tev1={rt['choice']:<8} decide={d['action']:<8} spans={len(det['spans'])}  "
                  f"{'; '.join(d['reasons'])}" + (f"  ⚠ {d['warnings'][0][:30]}" if d["warnings"] else ""), flush=True)
        n = len(rows)
        ok_rule = sum(conf_rule[g][g] for g in conf_rule)
        ok_tev = sum(conf_tev[g][g] for g in conf_tev)
        blk_gold = sum(conf_rule["block"].values())
        blk_hit = conf_rule["block"]["block"]
        false_blk = sum(conf_rule[g]["block"] for g in conf_rule if g != "block")
        md += [f"## {Path(f).name} · {n}건", "",
               f"- 경로 일치: 규칙 포함 {ok_rule}/{n} ({ok_rule / n:.0%}) · tev1만 {ok_tev}/{n} ({ok_tev / n:.0%})",
               f"- 차단: 정답 {blk_gold}건 중 {blk_hit}건 차단 · 잘못 차단 {false_blk}건",
               f"- 지시 삽입 경고 {len(warn_ids)}건 ({', '.join(warn_ids) or '-'}) · 내부 전용 정책으로 local {internal_n}건", "",
               "| 정답 \\ 결정 | local | external | block |", "|---|---|---|---|"]
        for g in ["local", "external", "block"]:
            if conf_rule[g]:
                md.append(f"| {g} | {conf_rule[g]['local']} | {conf_rule[g]['external']} | {conf_rule[g]['block']} |")
        md += ["", "불일치:"] + ([f"- {m}" for m in mism] or ["- 없음"]) + [""]
    text = "\n".join(md)
    print("\n" + text)
    out = RESULTS / f"decide_check_{datetime.now():%Y%m%d_%H%M}.md"
    out.write_text(text, encoding="utf-8")
    print("저장:", out)


if __name__ == "__main__":
    main()
