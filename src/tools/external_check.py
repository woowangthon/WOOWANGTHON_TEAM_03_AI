"""외부 LLM 경로 점검: 시연 문서(외부 경로 D3·D4·D6)와 TEST-01 을 탐지 → 가림 → 유출 검사 → Anthropic → 복원으로 돌려
자리표가 답변에 유지되고 원문으로 되돌아오는지, 시간과 비용이 얼마인지 본다. 모델 품질(번역이 좋은지)은 사람이 결과 파일에서 본다.

사용: .venv\\Scripts\\python.exe src\\tools\\external_check.py [--smoke] [--ids D3,D4,D6,TEST-01] [--model claude-sonnet-5-5] [--effort medium] [--no-fallback] [--no-llm]
  --smoke   짧은 문장 1회만 보내 키·모델·자리표 유지가 되는지 본다 (비용 거의 0)
  --no-llm  탐지에 30B 를 쓰지 않음 (Ollama 없이 외부 경로만 점검)
결과: src/results/external_check_<stamp>.md
키: 환경변수 ANTHROPIC_API_KEY. 결과 파일에는 키·요청 id 외 비밀이 들어가지 않는다.
"""
import argparse
import json
import sys
import time
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import anthropic  # noqa: E402

from answer_external import MODEL, EFFORT, answer_external, has_key, leak_check, run_external  # noqa: E402
from common import RESULTS, ROOT, find_all, load_samples, utf8_stdout  # noqa: E402
from detect import detect  # noqa: E402
from extract import extract_pdf  # noqa: E402

DEMO = ROOT / "data" / "demo" / "demo_docs_v1.jsonl"
ACCEPT = ROOT / "data" / "accept" / "TEST-01.json"
PROJECT = ROOT.parent


def load_docs(ids):
    docs = {r["id"]: {"id": r["id"], "case": r["case"], "text": r["text"], "route": r["route"]} for r in load_samples(DEMO)}
    out = []
    for i in ids:
        if i == "TEST-01":
            spec = json.loads(ACCEPT.read_text(encoding="utf-8"))
            pdf = PROJECT / spec["pdf"]
            ex = extract_pdf(pdf)
            out.append({"id": "TEST-01", "case": spec.get("title", ""), "route": "external(강제)",
                        "text": spec["instruction"].strip() + "\n\n" + ex["text"]})
        elif i in docs:
            out.append(docs[i])
        else:
            print(f"모르는 문서 id: {i}", flush=True)
    return out


def smoke(model, effort, fallback):
    r = answer_external("[[ORG_1]] 담당자에게 보낼 인사 한 문장을 써 주세요. 자리표는 그대로 두세요.", {"[[ORG_1]]": "한빛에어로"},
                        model=model, effort=effort, fallback=fallback)
    ok = r["stop_reason"] == "end_turn" and r["placeholders"]["kept"] == 1 and "한빛에어로" in r["restored"] and not r["unresolved"]
    print(f"{'O' if ok else 'X'} smoke: {r['served_by']} · {r['stop_reason']} · 자리표 {r['placeholders']} · 복원 '{r['restored'][:80]}' · "
          f"토큰 {r['usage']['input_tokens']}/{r['usage']['output_tokens']} · ${r['cost_usd']} · {r['seconds']}s · {r['notes'] or ''}", flush=True)
    return ok, r


def main():
    utf8_stdout()
    ap = argparse.ArgumentParser()
    ap.add_argument("--smoke", action="store_true")
    ap.add_argument("--ids", default="D3,D4,D6,TEST-01")
    ap.add_argument("--model", default=MODEL)
    ap.add_argument("--effort", default=EFFORT)
    ap.add_argument("--no-fallback", action="store_true")
    ap.add_argument("--no-llm", action="store_true")
    a = ap.parse_args()
    if not has_key():
        sys.exit("ANTHROPIC_API_KEY 가 없다. 별도 PowerShell 창에서 setx ANTHROPIC_API_KEY \"<키>\" 로 등록한 뒤 다시 실행.")
    fallback = not a.no_fallback
    stamp = datetime.now().strftime("%Y%m%d_%H%M")

    try:
        ok, sm = smoke(a.model, a.effort, fallback)
    except anthropic.AuthenticationError:
        sys.exit("키가 틀리거나 만료됨 (401)")
    except anthropic.APIStatusError as e:
        sys.exit(f"API 오류 {e.status_code}: {str(e)[:300]}")
    if a.smoke:
        return

    rows = []
    for d in load_docs(a.ids.split(",")):
        t0 = time.perf_counter()
        det = detect(d["text"], use_llm=not a.no_llm)
        det_s = round(time.perf_counter() - t0, 2)
        row = {"id": d["id"], "case": d["case"], "route": d["route"], "chars": len(d["text"]), "spans": len(det["spans"]), "det_s": det_s}
        try:
            r = run_external(d["text"], det["spans"], model=a.model, effort=a.effort, fallback=fallback)
        except ValueError as e:  # 유출 검사에 걸림
            row.update({"error": str(e)})
            rows.append(row)
            print(f"X {d['id']}: {e}", flush=True)
            continue
        except anthropic.APIStatusError as e:
            row.update({"error": f"API {e.status_code}: {str(e)[:200]}"})
            rows.append(row)
            print(f"X {d['id']}: {row['error']}", flush=True)
            continue
        originals = [v for v in r["mapping"].values()]
        back = sum(1 for v in set(originals) if v in r["restored"])
        row.update({
            "masked": len(r["entries"]), "sent": r["placeholders"]["sent"], "kept": r["placeholders"]["kept"],
            "unresolved": len(r["unresolved"]), "back": back, "distinct": len(set(originals)),
            "leaks": len(leak_check(r["masked"], r["mapping"])),
            "stop": r["stop_reason"], "served_by": r["served_by"], "fallback_ran": r["fallback_ran"], "refusal": r["refusal"],
            "in": r["usage"]["input_tokens"], "out": r["usage"]["output_tokens"], "cost": r["cost_usd"], "api_s": r["seconds"],
            "answer": r["answer"], "restored": r["restored"], "masked_text": r["masked"], "notes": r["notes"],
        })
        rows.append(row)
        print(f"{'O' if row['stop'] == 'end_turn' and not row['unresolved'] else 'X'} {d['id']}: 구간 {row['spans']} 가림 {row['masked']} · "
              f"자리표 보냄 {row['sent']} 유지 {row['kept']} · 미복원 {row['unresolved']} · 원문 복귀 {back}/{row['distinct']} · "
              f"{row['stop']} · 토큰 {row['in']}/{row['out']} · ${row['cost']} · 탐지 {det_s}s API {row['api_s']}s", flush=True)

    total_cost = round(sum(r.get("cost") or 0 for r in rows) + (sm["cost_usd"] or 0), 4)
    md = [f"# 외부 LLM 경로 점검 · {stamp}", "",
          f"모델 {a.model} · effort {a.effort} · fallback {'켬' if fallback else '끔'} · 탐지 {'규칙+NER' if a.no_llm else '규칙+NER+30B'} · 가림 정책 기본(이름 끔). "
          f"총 비용(추정) ${total_cost}. smoke: {sm['served_by']} {sm['stop_reason']} 자리표 {sm['placeholders']} {sm['seconds']}s", "",
          "| 문서 | 경로 | 자 | 구간 | 가림 | 자리표 보냄 | 답변에 유지 | 미복원 | 원문 복귀 | 유출 | 종료 | 응답 모델 | 입력/출력 토큰 | $ | 탐지 s | API s |",
          "|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|"]
    for r in rows:
        if r.get("error"):
            md.append(f"| {r['id']} | {r['route']} | {r['chars']:,} | {r['spans']} | - | - | - | - | - | - | 오류 | - | - | - | {r['det_s']} | - |")
            continue
        md.append(f"| {r['id']} | {r['route']} | {r['chars']:,} | {r['spans']} | {r['masked']} | {r['sent']} | {r['kept']} | {r['unresolved']} | "
                  f"{r['back']}/{r['distinct']} | {r['leaks']} | {r['stop']}{' (대체 모델)' if r['fallback_ran'] else ''} | {r['served_by']} | "
                  f"{r['in']}/{r['out']} | {r['cost']} | {r['det_s']} | {r['api_s']} |")
    md += ["", "열 설명: 자리표 보냄 = 가림 본문의 자리표 종류 수, 답변에 유지 = 그중 답변에 그대로 남은 수(요약이면 전부 안 나와도 정상), "
           "미복원 = 복원 뒤에도 남은 자리표(대응표에 없는 것, 0이어야 함), 원문 복귀 = 복원 답변에 원문 값이 나타난 종류 수, 유출 = 전송 본문에 남은 원문 값(0이어야 함).", ""]
    for r in rows:
        if r.get("error"):
            md += [f"## {r['id']} · 오류", "", r["error"], ""]
            continue
        md += [f"## {r['id']} · {r['case']}", "", f"- 가림 정책: 이름 끔 · 종료 {r['stop']} · 응답 모델 {r['served_by']}" + (f" · 메모 {r['notes']}" if r["notes"] else ""),
               "", "### 외부로 나간 본문", "", "```", r["masked_text"], "```", "", "### 복원된 답변", "", "```", r["restored"], "```", ""]
        if r["unresolved"]:
            md.append(f"- 미복원 자리표: {r['unresolved']}")
        if r["refusal"]:
            md.append(f"- 거부: {r['refusal']}")
    out = RESULTS / f"external_check_{stamp}.md"
    out.write_text("\n".join(md) + "\n", encoding="utf-8")
    print(f"총 비용(추정) ${total_cost} · 결과: {out}", flush=True)


if __name__ == "__main__":
    main()
