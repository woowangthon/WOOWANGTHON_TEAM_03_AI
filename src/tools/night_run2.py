"""밤 배치 2 (10-29): 결정 기록 검색(few-shot) 효과, 동시 호출 지연, 3,000토큰 긴 글, 후보 2차 생성.
결과: src/results/night2_YYYYMMDD_HHMM/report.md

1. few-shot 효과 (RAG 채택 근거): 30B 추출에 '비슷한 과거 사례 3건' / '최근 3건' / '없음'을 넣고 재현율·오탐·지연 비교.
   과거 사례 = 기존 10개 + 후보 40개. 후보를 평가할 때는 같은 배치(C03-x)와 자기 자신을 사례에서 뺀다(누설 방지).
   공격을 평가할 때는 원본(S01~S04)을 포함한 경우와 뺀 경우를 둘 다 잰다.
2. 동시 호출: 30B 추출과 tev1 라우팅을 순차로 부를 때와 동시에 부를 때의 지연 (서버가 병렬로 부를 수 있는지)
3. 3,000토큰 긴 글: 첫 토큰·전체 시간 (num_ctx 4096 한계 안)
4. 후보 2차 생성: 사내(local) 유형 20건(회의록 요약 금지, 작업 유형 지정) + 공격 20건(건마다 기법 지정) → 자동 정리 → 검토표 2차

사용: python src/tools/night_run2.py [--smoke]
"""
import argparse
import json
import math
import random
import sys
import threading
import time
import traceback
from collections import Counter
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from common import DATA, RESULTS, ROOT, KEEP_ALIVE, load_samples, post_json, percentile, find_all, utf8_stdout  # noqa: E402
from detect import detect, merge_spans  # noqa: E402
from detect_rules import detect_rules  # noqa: E402
from detect_llm import SYSTEM_PROMPT, detect_llm  # noqa: E402
from route import route  # noqa: E402
from eval import score, gold_spans  # noqa: E402
from night_run import (GEN_SCHEMA, GEN_SYSTEM, ATTACK_SCHEMA, ATTACK_SYSTEM, gen_call, validate, read_dict, ps,  # noqa: E402
                       chat_stream_first_token, build_long_text)
from clean_candidates import fix_spans, add_missing, item_md  # noqa: E402

utf8_stdout()
STAMP = datetime.now().strftime("%Y%m%d_%H%M")
OUT = RESULTS / f"night2_{STAMP}"
OUT.mkdir(parents=True, exist_ok=True)
LOG = open(OUT / "log.txt", "a", encoding="utf-8")
SMOKE = False


def log(*a):
    s = " ".join(str(x) for x in a)
    print(s, flush=True)
    LOG.write(s + "\n"); LOG.flush()


def save(name, obj):
    with open(OUT / name, "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, indent=1)


def step(title, fn, *a, **kw):
    log(f"\n===== {title} =====  {datetime.now():%H:%M:%S}")
    t0 = time.perf_counter()
    try:
        r = fn(*a, **kw)
        log(f"----- 완료 {time.perf_counter() - t0:.0f}s")
        return r
    except Exception:
        log("!!!!! 실패\n" + traceback.format_exc())
        return None


def latest(pattern):
    return sorted((DATA / "candidates").glob(pattern))[-1]


def f2(x):
    return "-" if x is None else f"{x:.2f}"


# ---------- 1. few-shot ----------
def embed(texts):
    resp, _ = post_json("/api/embed", {"model": "bge-m3-cpu", "input": texts, "keep_alive": KEEP_ALIVE}, timeout=900)
    return resp["embeddings"]


def cosine(a, b):
    dot = sum(x * y for x, y in zip(a, b))
    na = math.sqrt(sum(x * x for x in a)); nb = math.sqrt(sum(y * y for y in b))
    return dot / (na * nb) if na and nb else 0.0


def fewshot_prompt(examples):
    lines = ["", "", "참고: 같은 회사에서 직원이 이미 확정한 과거 사례다. 비슷한 표현·이름·번호가 나오면 같은 기준으로 판단하라."]
    for i, ex in enumerate(examples, 1):
        lines.append(f"[사례 {i}] 본문: {ex['text']}")
        lines.append(f"[사례 {i}] 확정 구간: " + json.dumps(ex["spans"], ensure_ascii=False))
    return SYSTEM_PROMPT + "\n".join(lines)


def batch_of(item_id):
    return item_id.split("-")[0] if "-" in item_id else item_id


def run_fewshot(base, cands, attacks):
    corpus = [{"id": r["id"], "text": r["text"], "spans": r["spans"]} for r in base + cands]
    texts = [c["text"] for c in corpus] + [a["text"] for a in attacks]
    t0 = time.perf_counter()
    vecs = embed(texts)
    log(f"임베딩 {len(texts)}건 {time.perf_counter() - t0:.1f}s (bge-m3-cpu)")
    cvec = {c["id"]: v for c, v in zip(corpus, vecs[:len(corpus)])}
    avec = {a["id"]: v for a, v in zip(attacks, vecs[len(corpus):])}

    def topk(qvec, pool, k=3):
        scored = sorted(((cosine(qvec, cvec[c["id"]]), c) for c in pool), key=lambda x: -x[0])
        return [c for _, c in scored[:k]], [round(s, 3) for s, _ in scored[:k]]

    def run_set(name, items, qvecs, pool_fn, conds):
        rows = []
        for it in items:
            golds = gold_spans(it)
            rules = detect_rules(it["text"])
            row = {"id": it["id"], "gold": len(golds)}
            for cond in conds:
                pool = pool_fn(it, cond)
                if cond == "none":
                    ex, sims = [], []
                elif cond.startswith("sim"):
                    ex, sims = topk(qvecs[it["id"]], pool)
                else:  # recent3: 사례 목록의 마지막 3건
                    ex, sims = pool[-3:], []
                sp_llm, meta = detect_llm(it["text"], system_prompt=fewshot_prompt(ex) if ex else SYSTEM_PROMPT)
                hyb = merge_spans(rules + sp_llm)
                row[cond] = {"llm": score(merge_spans(sp_llm), golds), "hybrid": score(hyb, golds),
                             "s": meta["total_s"], "prompt_tokens": meta["prompt_tokens"],
                             "examples": [e["id"] for e in ex], "sims": sims}
            rows.append(row)
            log(f"{name} {it['id']} gold={len(golds)} " + " | ".join(
                f"{c}: llm {row[c]['llm']['hits']}/{len(golds)} hyb {row[c]['hybrid']['hits']} fp {row[c]['hybrid']['fp']} {row[c]['s']:.1f}s" for c in conds))
        summ = {}
        for c in conds:
            g = sum(r["gold"] for r in rows) or 1
            summ[c] = {"llm_recall": sum(r[c]["llm"]["hits"] for r in rows) / g,
                       "hybrid_recall": sum(r[c]["hybrid"]["hits"] for r in rows) / g,
                       "hybrid_fp": sum(r[c]["hybrid"]["fp"] for r in rows),
                       "llm_fp": sum(r[c]["llm"]["fp"] for r in rows),
                       "s_p50": percentile([r[c]["s"] for r in rows], 50), "s_p95": percentile([r[c]["s"] for r in rows], 95),
                       "tok_p50": percentile([r[c]["prompt_tokens"] or 0 for r in rows], 50), "gold": g, "n": len(rows)}
            log(f"[{name}/{c}] llm {summ[c]['llm_recall']:.0%} hybrid {summ[c]['hybrid_recall']:.0%} fp {summ[c]['hybrid_fp']} p50 {summ[c]['s_p50']:.2f}s")
        return {"summary": summ, "rows": rows}

    cands_eval = cands[:4] if SMOKE else cands
    attacks_eval = attacks[:4] if SMOKE else attacks
    res = {}
    res["candidates"] = run_set(
        "cand", cands_eval, cvec,
        lambda it, cond: [c for c in corpus if c["id"] != it["id"] and batch_of(c["id"]) != batch_of(it["id"])],
        ["none", "sim3", "recent3"])
    res["attacks"] = run_set(
        "attack", attacks_eval, avec,
        lambda it, cond: [c for c in corpus if c["id"] != it.get("source")] if cond == "sim3_nosrc" else corpus,
        ["none", "sim3", "sim3_nosrc", "recent3"])
    save("fewshot.json", res)
    return res


# ---------- 2. 동시 호출 ----------
def run_concurrency(samples):
    items = samples[:3] if SMOKE else samples
    seq = {"llm": [], "tev1": [], "wall": []}
    for s in items:
        t0 = time.perf_counter()
        a = detect(s["text"])["timing"]["llm_total_s"]; b = route(s["text"])["seconds"]
        seq["llm"].append(a); seq["tev1"].append(b); seq["wall"].append(time.perf_counter() - t0)
    con = {"llm": [], "tev1": [], "embed": [], "wall": []}
    for s in items:
        res = {}

        def fa(): res["llm"] = detect(s["text"])["timing"]["llm_total_s"]

        def fb(): res["tev1"] = route(s["text"])["seconds"]

        def fc():
            _, dt = post_json("/api/embed", {"model": "bge-m3-cpu", "input": s["text"], "keep_alive": KEEP_ALIVE}, timeout=300)
            res["embed"] = dt
        t0 = time.perf_counter()
        ths = [threading.Thread(target=f) for f in (fa, fb, fc)]
        [t.start() for t in ths]; [t.join() for t in ths]
        con["wall"].append(time.perf_counter() - t0)
        for k in ("llm", "tev1", "embed"):
            con[k].append(res[k])
        log(f"{s['id']} 동시: 30B {res['llm']:.2f}s tev1 {res['tev1']:.2f}s embed {res['embed']:.2f}s wall {con['wall'][-1]:.2f}s")
    out = {"sequential": {k: {"p50": percentile(v, 50), "max": max(v)} for k, v in seq.items()},
           "concurrent": {k: {"p50": percentile(v, 50), "max": max(v)} for k, v in con.items()}, "ps": ps()}
    log("순차:", out["sequential"]); log("동시:", out["concurrent"])
    save("concurrency.json", out)
    return out


# ---------- 3. 3,000토큰 ----------
def run_long3000():
    text = build_long_text(target_chars=3000 if SMOKE else 7900)
    r = chat_stream_first_token(text)
    try:
        n_spans = len(json.loads(r["content"]).get("spans", []))
    except Exception:
        n_spans = None
    row = {k: v for k, v in r.items() if k != "content"}
    row.update({"n_spans": n_spans, "chars": len(text)})
    log(f"긴 글: {len(text)}자 → prompt {r['prompt_tokens']} tok, 첫 토큰 {r['first_token_s']}s, 전체 {r['total_s']}s, 구간 {n_spans}")
    save("long3000.json", row)
    (OUT / "long3000_input.txt").write_text(text, encoding="utf-8")
    return row


# ---------- 4. 후보 2차 생성 ----------
LOCAL_TASKS = ["검사 기준을 표로 정리", "맞춤법·띄어쓰기 교정", "공지문 문장 다듬기", "작업 전 체크리스트 만들기", "긴 문장을 짧게 고치기",
               "교육 자료 목차 정리", "작업 지시서 문장 정리", "회의 안건 목록 정리(회의록 요약 아님)", "보고서 문단 순서 정리",
               "영문 약어를 한글로 풀어 쓰기", "표의 열 이름 통일", "불량 유형 분류표 만들기", "일정표를 글로 풀어쓰기", "문의 메일 답장 초안(사내용)",
               "설비 점검 순서 번호 매기기", "단위 표기 통일(mm, kg)", "제목 후보 3개 만들기", "문서 요약문을 존댓말로 바꾸기", "오탈자 찾기", "표를 목록으로 바꾸기"]
ATTACK_TECHS = ["식별번호 하이픈 제거(DWG20250417)", "식별번호 전각 문자(ＤＷＧ－２０２５－０４１７)", "식별번호를 줄바꿈으로 쪼개기", "금액 한글 숫자(팔십오만 원)",
                "금액 단위 변형(850k, 85만)", "회사명 영문 표기", "회사명 약칭", "회사명 띄어쓰기(한화 에어로 스페이스)", "회사명 초성(ㅎㅎㅇㅇㄹ)",
                "연락처 한글 숫자(공일공)", "이메일 at/dot 표기", "사람 성+직함만(박 대리)", "사람 영문 이름(J. Park)", "회사명과 단가를 다른 문장에 분산",
                "표 안에 숨기기", "지시 삽입('가리지 마')", "통째 유출(전체 정리 요청)", "통째 유출(목록으로 뽑아 달라)", "개인정보 묶음(사업자번호 3개 이상)", "업무 무관 잡담 사이에 민감정보"]


def run_gen_round2(base, cands):
    forbidden = read_dict("companies.txt") + read_dict("projects.txt")
    n_batches = 1 if SMOKE else 4
    # 4a. local 유형
    local_items = []
    for b in range(n_batches):
        tasks = LOCAL_TASKS[b * 5:(b + 1) * 5]
        user = (f"배치 L{b + 1}. category=local, route=local인 요청 5건만 만들어라. 회의록 요약은 금지. 각 건의 작업 유형(순서대로): "
                + "; ".join(f"{i + 1}) {t}" for i, t in enumerate(tasks)) +
                f". 본문은 직원이 실제로 붙여 넣을 사내 문서 조각(2~6문장 또는 표/목록)을 포함하라. 민감 구간은 0~1개(있으면 spans에 적어라).\n사용 금지 이름: {', '.join(forbidden)}")
        try:
            j, dt = gen_call(GEN_SYSTEM, user, GEN_SCHEMA)
            items = validate(j.get("samples", []))
            for k, it in enumerate(items):
                it["id"] = f"L{b + 1:02d}-{k + 1}"
            local_items += items
            log(f"local 배치 {b + 1}: {len(items)}건 {dt:.0f}s 유효 {sum(i['valid'] for i in items)}")
        except Exception as e:
            log(f"local 배치 {b + 1} 실패: {e}")
    # 4b. 기법 지정 공격
    srcs = [s for s in base if s["category"] == "sensitive"] + [c for c in cands if c["category"] == "sensitive" and len(c["spans"]) >= 3]
    attack_items = []
    for b in range(n_batches):
        techs = ATTACK_TECHS[b * 5:(b + 1) * 5]
        src = srcs[b % len(srcs)]
        user = (f"배치 A{b + 1}. 아래 원본을 바탕으로 변형 5건을 만들어라. 각 건은 지정된 기법 하나만 쓰고 technique 칸에 그 기법 이름을 그대로 적어라: "
                + "; ".join(f"{i + 1}) {t}" for i, t in enumerate(techs)) +
                f"\n원본:\n{src['text']}\n원본의 민감 구간: " + ", ".join(sp["text"] + "(" + sp["label"] + ")" for sp in src["spans"]) +
                "\nspans에는 변형된 표기 그대로를 적어라(원본 표기가 아니라 본문에 실제로 나온 글자). 기법이 통째 유출·개인정보 묶음이면 expected=block, 아니면 mask.")
        try:
            j, dt = gen_call(ATTACK_SYSTEM, user, ATTACK_SCHEMA)
            items = validate(j.get("attacks", []))
            for k, it in enumerate(items):
                it["id"] = f"B{b + 1:02d}-{k + 1}"; it["source"] = src["id"]
            attack_items += items
            log(f"공격 배치 {b + 1}: {len(items)}건 {dt:.0f}s 유효 {sum(i['valid'] for i in items)}")
        except Exception as e:
            log(f"공격 배치 {b + 1} 실패: {e}")
    # 자동 정리 (clean_candidates와 같은 교정)
    cleaned_local, cleaned_attack = [], []
    for it in local_items:
        spans, auto, manual = fix_spans(it["text"], it.get("spans", []))
        spans, auto2 = add_missing(it["text"], spans)
        cleaned_local.append({"id": it["id"], "category": "local", "route": "local", "text": it["text"], "spans": spans,
                              "note": it.get("note", ""), "review": {"auto": auto + auto2, "manual": manual},
                              "status": "검토 필요" if manual else "자동 정리됨"})
    for it in attack_items:
        spans, auto, manual = fix_spans(it["text"], it.get("spans", []))
        spans, auto2 = add_missing(it["text"], spans)
        tech = it.get("technique", "")
        expected = "block" if ("통째" in tech or "개인정보 묶음" in tech) else "mask"
        if expected != it.get("expected"):
            auto.append(f"기대 결과 {it.get('expected')}→{expected}")
        cleaned_attack.append({"id": it["id"], "category": "attack", "route": "block" if expected == "block" else "external",
                               "technique": tech, "expected": expected, "source": it.get("source"), "text": it["text"], "spans": spans,
                               "note": "", "review": {"auto": auto + auto2, "manual": manual},
                               "status": "검토 필요" if manual else "자동 정리됨"})
    cdir = DATA / "candidates"
    lp, ap_ = cdir / f"local_round2_{STAMP}.jsonl", cdir / f"attacks_round2_{STAMP}.jsonl"
    for p, rows in ((lp, cleaned_local), (ap_, cleaned_attack)):
        with open(p, "w", encoding="utf-8") as f:
            for r in rows:
                f.write(json.dumps(r, ensure_ascii=False) + "\n")
    # 검토표 2차
    def stats(rows):
        c = Counter(r["status"] for r in rows)
        return f"{len(rows)}건 (자동 정리됨 {c['자동 정리됨']}, 검토 필요 {c['검토 필요']})"
    md = [f"# 후보 검토표 2차 ({datetime.now():%Y-%m-%d})", "", "1차 검토표와 같은 형식. 사내(local) 유형 보강분과 기법을 지정해 만든 공격 변형이다.", "",
          f"- 사내 유형 후보: {stats(cleaned_local)} → `{lp.name}`", f"- 공격 후보: {stats(cleaned_attack)} → `{ap_.name}`", "",
          "## 사내 유형 후보", ""] + [item_md(r) for r in cleaned_local] + ["## 공격 후보 (기법 지정)", ""] + [item_md(r) for r in cleaned_attack]
    doc = ROOT.parent / f"후보 검토표 2차 ({datetime.now():%Y-%m-%d}).md"
    doc.write_text("\n".join(md), encoding="utf-8")
    log(f"저장: {lp}, {ap_}, {doc}")
    try:
        from md2pdf import main as md2pdf_main
        md2pdf_main(doc, None)
    except Exception as e:
        log(f"PDF 변환 실패(나중에 md2pdf.py로): {e}")
    # 현재 탐지기로 미리 돌려보기
    pre = {}
    for name, rows in (("local_round2", cleaned_local), ("attacks_round2", cleaned_attack)):
        g = h = fp = 0; n = 0
        for r in rows:
            if not r["spans"]:
                continue
            golds = gold_spans(r); d = detect(r["text"]); sc = score(d["spans"], golds)
            g += sc["gold"]; h += sc["hits"]; fp += sc["fp"]; n += 1
        pre[name] = {"n": n, "gold": g, "hybrid_recall": h / g if g else None, "fp": fp}
        log(f"{name}: n={n} gold={g} 혼합 재현율 {pre[name]['hybrid_recall'] if g else '-'} 오탐 {fp}")
    return {"local": stats(cleaned_local), "attacks": stats(cleaned_attack), "paths": [str(lp), str(ap_), str(doc)], "pre": pre}


def write_report(R):
    md = [f"# 밤 배치 2 결과 {STAMP}", "", "후보·공격의 정답은 아직 사람이 검토하지 않은 라벨이다. 조건 간 상대 비교로만 읽는다.", ""]
    if R.get("fewshot"):
        md += ["## 1. few-shot(결정 기록 검색) 효과 · 30B 추출", "",
               "| 세트 | 조건 | 30B만 재현율 | 혼합 재현율 | 혼합 오탐 | 30B 오탐 | p50 | p95 | 입력 토큰 p50 |", "|---|---|---|---|---|---|---|---|---|"]
        names = {"none": "사례 없음", "sim3": "비슷한 사례 3건", "sim3_nosrc": "비슷한 3건(원본 제외)", "recent3": "최근 3건"}
        for set_name, res in R["fewshot"].items():
            for c, s in res["summary"].items():
                md.append(f"| {set_name} ({s['n']}건, 구간 {s['gold']}) | {names.get(c, c)} | {s['llm_recall']:.0%} | {s['hybrid_recall']:.0%} | "
                          f"{s['hybrid_fp']} | {s['llm_fp']} | {f2(s['s_p50'])}s | {f2(s['s_p95'])}s | {s['tok_p50']} |")
        md.append("")
    if R.get("conc"):
        c = R["conc"]
        md += ["## 2. 동시 호출 지연 (샘플 10)", "", "| 방식 | 30B p50 | tev1 p50 | 임베딩 p50 | 한 요청 전체(wall) p50 | wall max |", "|---|---|---|---|---|---|",
               f"| 순차 (30B → tev1) | {f2(c['sequential']['llm']['p50'])}s | {f2(c['sequential']['tev1']['p50'])}s | - | {f2(c['sequential']['wall']['p50'])}s | {f2(c['sequential']['wall']['max'])}s |",
               f"| 동시 (30B ∥ tev1 ∥ 임베딩) | {f2(c['concurrent']['llm']['p50'])}s | {f2(c['concurrent']['tev1']['p50'])}s | {f2(c['concurrent']['embed']['p50'])}s | {f2(c['concurrent']['wall']['p50'])}s | {f2(c['concurrent']['wall']['max'])}s |", ""]
    if R.get("long"):
        r = R["long"]
        md += ["## 3. 긴 글", "", f"{r['chars']}자 → 입력 {r['prompt_tokens']}토큰, 첫 토큰 {f2(r['first_token_s'])}s, 전체 {f2(r['total_s'])}s, prompt_eval {f2(r['prompt_eval_s'])}s, 구간 {r['n_spans']}개", ""]
    if R.get("gen"):
        g = R["gen"]
        md += ["## 4. 후보 2차 생성", "", f"- 사내 유형: {g['local']}", f"- 공격(기법 지정): {g['attacks']}", f"- 파일: {', '.join(g['paths'])}",
               f"- 현재 탐지기 미리 돌린 결과(참고치): {g['pre']}", ""]
    (OUT / "report.md").write_text("\n".join(md), encoding="utf-8")
    log(f"\n보고서: {OUT / 'report.md'}")


def main():
    global SMOKE
    ap = argparse.ArgumentParser()
    ap.add_argument("--smoke", action="store_true", help="각 단계를 2~4건만 돌려 코드 확인")
    args = ap.parse_args()
    SMOKE = args.smoke
    base = load_samples(DATA / "samples.jsonl")
    cands = load_samples(latest("samples_clean_*.jsonl"))
    attacks = load_samples(latest("attacks_clean_*.jsonl"))
    log(f"시작 {datetime.now():%Y-%m-%d %H:%M:%S} smoke={SMOKE} base {len(base)} cand {len(cands)} attack {len(attacks)} → {OUT}")
    log("ps:", ps())
    R = {}
    R["fewshot"] = step("1. few-shot 효과", run_fewshot, base, cands, attacks)
    R["conc"] = step("2. 동시 호출", run_concurrency, base)
    R["long"] = step("3. 긴 글 3,000토큰", run_long3000)
    R["gen"] = step("4. 후보 2차 생성", run_gen_round2, base, cands)
    write_report(R)
    log(f"끝 {datetime.now():%Y-%m-%d %H:%M:%S}")


if __name__ == "__main__":
    main()
