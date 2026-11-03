"""실제 형태 문서 수락 검사 (11-01): 문서(PDF 또는 마크다운) + 정답표(json) → 글자 추출 → 탐지(규칙+NER+30B) → 경로 → 결정 → 가림(이름 토글 끔/켬) → 정답표 대조.

정답표 json: {id, [pdf], instruction, [route], tier1:[{label,text}], tier2:[{text}], [keep:[...]], [dict_companies], [dict_projects]}
  - pdf가 없으면 json 옆의 <id>.md 또는 <id>.pdf를 쓴다. md는 PDF로 바꿔(Edge 인쇄, 없으면 Word) 거기서 글자를 뽑는다. 실제 입력 경로와 같게 하기 위해서다.
  - 횟수·위치는 적지 않는다. 스크립트가 본문에서 센다. 정답 값이 본문에 글자 그대로 없으면 '정답 오류'로 따로 센다.
검사 기준(정답표 문서의 통과 기준 그대로):
  - 1등급 원문 값이 가린 본문에 남지 않는가 (값별 등장 수 / 가린 수 / 남은 수)
  - 유지 항목(3등급)은 가린 본문에 그대로 있는가
  - 같은 회사는 같은 자리표인가
  - 이름 토글 끔: 이름 유지 / 켬: 이름만 가리고 직급은 유지
  - 과잉 가림: 정답표에 없는 구간을 가린 것
  - route가 있으면 결정(decide)과 비교
실행은 두 가지: 사전 없음(cold) / 등록 후(dict: dict_companies·dict_projects, 없으면 정답표의 회사·사업명을 등록한 것으로 본다).
사전 파일은 건드리지 않고 이번 실행에만 등록어를 더한다(제품에서는 /dict/reload).

사용: python src/tools/accept_run.py <json 또는 폴더> [...] [--runs cold,dict] [--no-llm]
결과: 한 건이면 src/results/accept_<id>_<stamp>.md(+.json, 상세), 여러 건이면 src/results/accept_batch_<stamp>.md(+.json, 표 + 실패 상세)
"""
import argparse
import json
import subprocess
import sys
import tempfile
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import detect_rules as dr  # noqa: E402
from common import LABEL_KO, RESULTS, ROOT, find_all, utf8_stdout  # noqa: E402
from decide import decide  # noqa: E402
from detect import detect  # noqa: E402
from extract import extract_pdf  # noqa: E402
from mask import mask  # noqa: E402
from route import route  # noqa: E402

PROJECT = ROOT.parent
ACCEPT = ROOT / "data" / "accept"
RUN_NAME = {"cold": "사전 없음", "dict": "등록 후"}
EDGE = [r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe", r"C:\Program Files\Microsoft\Edge\Application\msedge.exe"]
CSS = """body{font-family:'Malgun Gothic',sans-serif;font-size:10.5pt;line-height:1.5}h1{font-size:18pt}h2{font-size:14pt;margin-top:18pt}
h3{font-size:12pt;margin-top:12pt}table{border-collapse:collapse;width:100%;font-size:9.5pt}th,td{border:1px solid #999;padding:4px 6px;vertical-align:top}
th{background:#eef1f4}code{font-family:Consolas,monospace;font-size:9.5pt}"""


# ---------- 문서 준비 ----------

def md_to_pdf(md_path: Path, pdf_path: Path):
    """마크다운 → HTML → PDF. Edge 헤드리스 인쇄(머리말·꼬리말 없음), 없으면 Word COM(md2pdf)."""
    import markdown
    html = markdown.markdown(md_path.read_text(encoding="utf-8"), extensions=["tables", "fenced_code"])
    tmp = Path(tempfile.gettempdir()) / (md_path.stem + "_accept.html")
    tmp.write_text(f"<html><head><meta charset='utf-8'><style>{CSS}</style></head><body>{html}</body></html>", encoding="utf-8")
    edge = next((p for p in EDGE if Path(p).exists()), None)
    if edge:
        subprocess.run([edge, "--headless", "--disable-gpu", "--disable-extensions", "--no-pdf-header-footer",
                        f"--print-to-pdf={pdf_path}", tmp.as_uri()], capture_output=True, timeout=90)
    if not edge or not pdf_path.exists():
        from md2pdf import main as word_pdf
        word_pdf(md_path, pdf_path)
    tmp.unlink(missing_ok=True)


def doc_path(spec_path: Path, spec: dict) -> Path:
    """정답표가 가리키는 문서 파일. pdf 필드(프로젝트 루트 기준) > 옆의 <id>.pdf(md보다 새것) > 옆의 <id>.md(PDF로 변환)."""
    if spec.get("pdf"):
        p = PROJECT / spec["pdf"]
        if not p.exists():
            p = spec_path.parent / spec["pdf"]
        return p
    sid = spec["id"]
    pdf, md = spec_path.parent / f"{sid}.pdf", spec_path.parent / f"{sid}.md"
    if md.exists() and (not pdf.exists() or pdf.stat().st_mtime < md.stat().st_mtime):
        md_to_pdf(md, pdf)
    if pdf.exists():
        return pdf
    raise FileNotFoundError(f"{sid}: 문서 파일 없음 ({pdf.name} 또는 {md.name})")


# ---------- 사전 ----------

def set_dict(extra_companies, extra_projects, base):
    """이번 프로세스에서만 등록어를 더한다. base는 원래 DICTS 사본."""
    extra = {"companies.txt": extra_companies, "projects.txt": extra_projects}
    dr.DICTS[:] = [(name, label, terms + [(t, dr.term_regex(t)) for t in extra.get(name, [])]) for name, label, terms in base]


def dict_terms(spec):
    comp = spec.get("dict_companies")
    proj = spec.get("dict_projects")
    if comp is None:
        comp = [v["text"] for v in spec["tier1"] if v["label"] == "company"]
    if proj is None:
        proj = [v["text"] for v in spec["tier1"] if v["label"] == "project"]
    return comp, proj


# ---------- 대조 ----------

def overlap(a, b):
    return max(0, min(a[1], b[1]) - max(a[0], b[0]))


def check_values(text, masked_text, entries, values):
    """values: [{label,text}]. 값마다 등장 위치를 찾아 가린 구간과 대조한다."""
    rows = []
    for v in values:
        occs = find_all(text, v["text"])
        hit, partial, tags = 0, [], set()
        for occ in occs:
            best, best_e = 0, None
            for en in entries:
                o = overlap(occ, (en["start"], en["end"]))
                if o > best:
                    best, best_e = o, en
            if best > 0:
                hit += 1
                tags.add(best_e["placeholder"])
                if best < (occ[1] - occ[0]):
                    partial.append(best_e["text"])
        rows.append({"label": v["label"], "text": v["text"], "occ": len(occs), "hit": hit,
                     "remaining": len(find_all(masked_text, v["text"])) if occs else 0,
                     "tags": sorted(tags), "partial": sorted(set(partial))})
    return rows


def classify_entries(text, entries, gold_values):
    """가린 구간 중 정답과 겹치지 않는 것(과잉)."""
    gold_occ = []
    for v in gold_values:
        gold_occ += find_all(text, v["text"])
    return [en for en in entries if not any(overlap((en["start"], en["end"]), g) > 0 for g in gold_occ)]


def run_one(text, det, rt, spec, toggle_person):
    d = decide(text, det["spans"], rt)
    m = mask(text, det["spans"], {"mask_person": toggle_person})
    masked, entries = m["masked"], m["entries"]
    t1 = check_values(text, masked, entries, spec["tier1"])
    t2 = check_values(text, masked, entries, spec.get("tier2", []))
    keep = []
    for k in spec.get("keep", []):
        before, after = len(find_all(text, k)), len(find_all(masked, k))
        keep.append({"text": k, "before": before, "after": after, "ok": before == after})
    gold_all = spec["tier1"] + (spec.get("tier2", []) if toggle_person else [])
    extra = classify_entries(text, entries, gold_all)
    same_tag = all(len(r["tags"]) <= 1 for r in t1 if r["label"] == "company")
    valid1 = [r for r in t1 if r["occ"] > 0]
    return {
        "decision": d, "masked": masked, "mapping": m["mapping"], "unmasked": m["unmasked"],
        "tier1": t1, "tier2": t2, "keep": keep, "extra": extra, "same_tag": same_tag,
        "gold_missing": [r["text"] for r in t1 + t2 if r["occ"] == 0],
        "sum": {
            "values_total": len(valid1), "values_clean": sum(1 for r in valid1 if r["remaining"] == 0),
            "occ_total": sum(r["occ"] for r in valid1), "occ_hit": sum(r["hit"] for r in valid1),
            "remaining": sum(r["remaining"] for r in valid1),
            "keep_ok": sum(1 for k in keep if k["ok"]), "keep_total": len(keep), "extra": len(extra),
            "t2_remaining": sum(r["remaining"] for r in t2), "t2_occ": sum(r["occ"] for r in t2),
        },
    }


def toggle_ok(off, on):
    """끔: 이름 전부 남음 · 켬: 이름 전부 가림 + 유지 항목 보존."""
    so, sn = off["sum"], on["sum"]
    return so["t2_remaining"] == so["t2_occ"] and sn["t2_remaining"] == 0 and all(k["ok"] for k in on["keep"])


def fmt_spans(spans):
    return ", ".join(f"{LABEL_KO.get(sp.label, sp.label)}:{sp.text}[{','.join(sp.sources)}]" for sp in spans) or "-"


# ---------- 실행 ----------

def run_spec(spec_path: Path, runs, no_llm):
    spec = json.loads(spec_path.read_text(encoding="utf-8"))
    sid = spec["id"]
    pdf = doc_path(spec_path, spec)
    ex = extract_pdf(pdf)
    (spec_path.parent / f"{sid}.txt").write_text(ex["text"], encoding="utf-8")
    text = (spec.get("instruction", "") + "\n\n" + ex["text"]) if spec.get("instruction") else ex["text"]
    print(f"{sid}: {pdf.name} {len(ex['pages'])}쪽 {ex['chars']:,}자 + 지시문 → 전체 {len(text):,}자 · 추출 경고 {ex['warnings'] or '-'}", flush=True)

    rt = route(text)
    print(f"  경로 판정: {rt['choice']} {rt.get('probabilities')} {rt.get('seconds')}s", flush=True)

    base = list(dr.DICTS)
    results = {}
    for run in runs:
        if run == "dict":
            set_dict(*dict_terms(spec), base)
        else:
            dr.DICTS[:] = base
        det = detect(text, use_llm=not no_llm)
        tm = det["timing"]
        results[run] = {"spans": det["spans"], "timing": tm, "warnings": det["warnings"], "dropped": det["dropped"],
                        "off": run_one(text, det, rt, spec, False), "on": run_one(text, det, rt, spec, True)}
        s = results[run]["off"]["sum"]
        print(f"  [{run}] 구간 {len(det['spans'])} · 30B {tm.get('llm_total_s')}s · 토글 끔: 값 {s['values_clean']}/{s['values_total']} 깨끗 · "
              f"등장 {s['occ_hit']}/{s['occ_total']} · 남음 {s['remaining']} · 유지 {s['keep_ok']}/{s['keep_total']} · 과잉 {s['extra']} · "
              f"토글 {'O' if toggle_ok(results[run]['off'], results[run]['on']) else 'X'}", flush=True)
    dr.DICTS[:] = base
    return {"spec": spec, "spec_path": spec_path, "pdf": pdf, "extract": ex, "text": text, "route": rt, "results": results}


# ---------- 보고서 ----------

def detail_md(r):
    spec, ex, text, rt, results = r["spec"], r["extract"], r["text"], r["route"], r["results"]
    d0 = next(iter(results.values()))["off"]["decision"]
    sid = spec["id"]
    md = [f"## {sid} · {spec.get('title') or spec.get('type', '')}", "",
          f"- 입력: {r['pdf'].name} {len(ex['pages'])}쪽 {ex['chars']:,}자 + 지시문 → 전체 {len(text):,}자. 추출 경고: {'; '.join(ex['warnings']) or '-'}",
          f"- 경로 판정(tev1): {rt['choice']} · 확률 {rt.get('probabilities')} · {rt.get('seconds')}s",
          f"- 결정: {d0['action']} (기대 {spec.get('route', '-')}) · 승인 필요 {d0['needs_approval']} · 사유: {'; '.join(d0['reasons']) or '-'} · 경고: {'; '.join(d0['warnings']) or '-'}", ""]
    for run, x in results.items():
        tm, off, on = x["timing"], x["off"], x["on"]
        md += [f"### {RUN_NAME.get(run, run)}", "",
               f"- 시간: 규칙 {tm.get('rules_ms')}ms · NER {tm.get('ner_s')}s · 30B {tm.get('llm_total_s')}s (조각 {tm.get('chunks')}, 지시 삽입 지움 {tm.get('injection_blanked')})",
               f"- 탐지 경고: {'; '.join(x['warnings']) or '-'} · 30B가 지어낸 구간: {len(x['dropped'])}",
               f"- 탐지 구간 {len(x['spans'])}개: {fmt_spans(x['spans'])}", "",
               "| 유형 | 원문 값 | 등장 | 가림 | 남음 | 자리표 | 부분 가림 표기 |", "|---|---|---|---|---|---|---|"]
        for v in off["tier1"]:
            flag = " ✗" if v["remaining"] or not v["occ"] else ""
            md.append(f"| {LABEL_KO.get(v['label'], v['label'])} | {v['text']} | {v['occ']} | {v['hit']} | {v['remaining']}{flag} | "
                      f"{', '.join(v['tags']) or '-'} | {', '.join(v['partial']) or '-'} |")
        broken = [k for k in off["keep"] if not k["ok"]]
        md += ["", "- 유지 항목: " + ("전부 보존" if not broken else "깨짐 " + ", ".join(f"{k['text']}({k['before']}→{k['after']})" for k in broken)),
               "- 과잉 가림(토글 끔): " + ("없음" if not off["extra"] else ", ".join(f"{LABEL_KO.get(e['label'], e['label'])}:{e['text']}" for e in off["extra"])),
               "- 정답 값이 본문에 없음: " + (", ".join(off["gold_missing"]) or "없음")]
        for a, b in zip(off["tier2"], on["tier2"]):
            md.append(f"- 이름 {a['text']}: 끔 → 남음 {a['remaining']}/{a['occ']} · 켬 → 남음 {b['remaining']}/{b['occ']}")
        on_broken = [k for k in on["keep"] if not k["ok"]]
        md += ["- 켬 상태 유지 항목: " + ("전부 보존" if not on_broken else "깨짐 " + ", ".join(f"{k['text']}({k['before']}→{k['after']})" for k in on_broken)),
               "- 켬 상태 과잉 가림: " + ("없음" if not on["extra"] else ", ".join(f"{LABEL_KO.get(e['label'], e['label'])}:{e['text']}" for e in on["extra"])), ""]
    return md


def summary_row(r):
    spec, rt, results = r["spec"], r["route"], r["results"]
    d = next(iter(results.values()))["off"]["decision"]
    gold_route = spec.get("route")
    cells = [spec["id"], spec.get("type", "-"), str(len(r["extract"]["pages"])), f"{r['extract']['chars']:,}",
             gold_route or "-", rt["choice"], d["action"], ("O" if d["action"] == gold_route else "✗") if gold_route else "-"]
    for run in ("cold", "dict"):
        if run not in results:
            cells += ["-"] * 6
            continue
        x = results[run]
        s = x["off"]["sum"]
        cells += [f"{s['values_clean']}/{s['values_total']}", f"{s['occ_hit']}/{s['occ_total']}", str(s["remaining"]),
                  f"{s['keep_ok']}/{s['keep_total']}", str(s["extra"]), "O" if toggle_ok(x["off"], x["on"]) else "✗"]
    cells.append(str(next(iter(results.values()))["timing"].get("llm_total_s")))
    return cells


def failed(r):
    out = []
    spec, results = r["spec"], r["results"]
    d = next(iter(results.values()))["off"]["decision"]
    if spec.get("route") and d["action"] != spec["route"]:
        out.append(f"경로 {spec['route']}→{d['action']} ({'; '.join(d['reasons']) or '-'})")
    for run, x in results.items():
        off, on = x["off"], x["on"]
        rem = [f"{v['text']}({v['remaining']})" for v in off["tier1"] if v["remaining"]]
        if rem:
            out.append(f"[{run}] 남은 원문: " + ", ".join(rem))
        broken = [k["text"] for k in off["keep"] if not k["ok"]] + [k["text"] for k in on["keep"] if not k["ok"]]
        if broken:
            out.append(f"[{run}] 유지 항목 깨짐: " + ", ".join(dict.fromkeys(broken)))
        if off["extra"] or on["extra"]:
            ex = {f"{LABEL_KO.get(e['label'], e['label'])}:{e['text']}" for e in off["extra"] + on["extra"]}
            out.append(f"[{run}] 과잉 가림: " + ", ".join(sorted(ex)))
        if not toggle_ok(off, on):
            out.append(f"[{run}] 이름 토글 실패: " + ", ".join(f"{a['text']} 끔 {a['remaining']}/{a['occ']} 켬 {b['remaining']}/{b['occ']}"
                                                         for a, b in zip(off["tier2"], on["tier2"])))
        if off["gold_missing"]:
            out.append(f"정답 값이 본문에 없음: " + ", ".join(off["gold_missing"]))
            break
    return out


HEAD = ("| 문서 | 종류 | 쪽 | 자 | 기대 경로 | tev1 | 결정 | 일치 | "
        "[사전 없음] 값 깨끗 | 등장 가림 | 남음 | 유지 | 과잉 | 토글 | [등록 후] 값 깨끗 | 등장 가림 | 남음 | 유지 | 과잉 | 토글 | 30B 초 |")


def write_batch(rs, stamp, runs):
    n = len(rs)
    tot = {run: {"vt": 0, "vc": 0, "ot": 0, "oh": 0, "rem": 0, "keep_bad": 0, "extra": 0, "toggle_bad": 0} for run in runs}
    route_n = route_ok = 0
    block_gold = block_hit = block_wrong = 0
    gold_missing = []
    for r in rs:
        spec = r["spec"]
        d = next(iter(r["results"].values()))["off"]["decision"]
        if spec.get("route"):
            route_n += 1
            route_ok += d["action"] == spec["route"]
            block_gold += spec["route"] == "block"
            block_hit += spec["route"] == "block" and d["action"] == "block"
            block_wrong += spec["route"] != "block" and d["action"] == "block"
        for run in runs:
            x = r["results"][run]
            s = x["off"]["sum"]
            t = tot[run]
            t["vt"] += s["values_total"]; t["vc"] += s["values_clean"]; t["ot"] += s["occ_total"]; t["oh"] += s["occ_hit"]
            t["rem"] += s["remaining"]; t["extra"] += s["extra"]
            t["keep_bad"] += any(not k["ok"] for k in x["off"]["keep"] + x["on"]["keep"])
            t["toggle_bad"] += not toggle_ok(x["off"], x["on"])
            gold_missing += [f"{spec['id']}:{g}" for g in x["off"]["gold_missing"]]
    md = [f"# 수락 검사 묶음 · {n}건 · {stamp}", "",
          "탐지 규칙+NER+30B → tev1 → 결정 규칙 → 가림. 값·등장 수치는 이름 토글 끔 기준(1등급). '토글'은 끔에서 이름 유지·켬에서 이름만 가림·유지 항목 보존을 모두 만족하면 O.", ""]
    for run in runs:
        t = tot[run]
        md.append(f"- {RUN_NAME.get(run, run)}: 1등급 값 {t['vc']}/{t['vt']} 깨끗 ({t['vc'] / max(t['vt'], 1):.1%}) · 등장 {t['oh']}/{t['ot']} 가림 · 남은 원문 {t['rem']} · "
                  f"과잉 가림 {t['extra']} · 유지 항목 깨진 문서 {t['keep_bad']} · 이름 토글 실패 문서 {t['toggle_bad']}")
    if route_n:
        md.append(f"- 경로 일치 {route_ok}/{route_n} · 차단 적중 {block_hit}/{block_gold} · 잘못 차단 {block_wrong}")
    md.append(f"- 정답 값이 본문에 없음(정답표 수정 필요): {len(gold_missing)}건" + (" · " + ", ".join(gold_missing) if gold_missing else ""))
    md += ["", HEAD, "|" + "---|" * 21]
    for r in rs:
        md.append("| " + " | ".join(summary_row(r)) + " |")
    fails = [(r["spec"]["id"], failed(r)) for r in rs]
    fails = [(i, f) for i, f in fails if f]
    md += ["", f"## 실패·주의 {len(fails)}건", ""]
    for sid, f in fails:
        md.append(f"- {sid}: " + " / ".join(f))
    md.append("")
    for r in rs:
        if failed(r):
            md += detail_md(r)
    out = RESULTS / f"accept_batch_{stamp}"
    out.with_suffix(".md").write_text("\n".join(md), encoding="utf-8")
    dump = {r["spec"]["id"]: {"route": r["route"], "runs": {run: {"timing": x["timing"], "warnings": x["warnings"],
                                                                 "spans": [sp.to_dict() for sp in x["spans"]],
                                                                 "off": {k: v for k, v in x["off"].items() if k not in ("masked", "mapping")},
                                                                 "on": {k: v for k, v in x["on"].items() if k not in ("mapping",)}}
                                                           for run, x in r["results"].items()}} for r in rs}
    out.with_suffix(".json").write_text(json.dumps(dump, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"결과: {out.with_suffix('.md')}")


def write_single(r, stamp):
    spec = r["spec"]
    last = list(r["results"].values())[-1]
    md = [f"# 수락 검사 {spec['id']} · {stamp}", "", f"{spec.get('title', '')}. 정답표: {spec.get('source', r['spec_path'].name)}.", "",
          f"- {spec.get('route_note', '')}", ""]
    md += detail_md(r)
    md += ["## 외부 전송 직전 본문 (마지막 실행, 이름 토글 켬)", "", "```", last["on"]["masked"], "```", "",
           "자리표 대응: " + ", ".join(f"{k}={v}" for k, v in last["on"]["mapping"].items()), ""]
    out = RESULTS / f"accept_{spec['id']}_{stamp}"
    out.with_suffix(".md").write_text("\n".join(md), encoding="utf-8")
    dump = {"route": r["route"], "runs": {run: {"timing": x["timing"], "warnings": x["warnings"], "spans": [sp.to_dict() for sp in x["spans"]],
                                                "off": x["off"], "on": x["on"]} for run, x in r["results"].items()}}
    out.with_suffix(".json").write_text(json.dumps(dump, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"결과: {out.with_suffix('.md')}")


def main():
    utf8_stdout()
    ap = argparse.ArgumentParser()
    ap.add_argument("paths", nargs="+", help="정답표 json 또는 json이 든 폴더")
    ap.add_argument("--runs", default="cold,dict")
    ap.add_argument("--no-llm", action="store_true")
    a = ap.parse_args()
    runs = a.runs.split(",")
    specs = []
    for p in a.paths:
        p = Path(p)
        specs += sorted(p.glob("*.json")) if p.is_dir() else [p]
    stamp = datetime.now().strftime("%Y%m%d_%H%M")
    rs = []
    for i, sp in enumerate(specs, 1):
        print(f"({i}/{len(specs)})", end=" ", flush=True)
        try:
            rs.append(run_spec(sp, runs, a.no_llm))
        except Exception as e:  # 한 건이 깨져도 묶음은 계속
            print(f"{sp.name}: 실패 {type(e).__name__}: {str(e)[:200]}", flush=True)
    if not rs:
        return
    if len(rs) == 1:
        write_single(rs[0], stamp)
    else:
        write_batch(rs, stamp, runs)


if __name__ == "__main__":
    main()
