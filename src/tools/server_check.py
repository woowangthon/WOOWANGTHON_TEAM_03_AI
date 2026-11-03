"""모델 서비스 점검: server.py 를 띄우고 HTTP 로 시연 6건과 TEST-01 을 넣어 직접 호출과 같은 결과가 나오는지, 인증·동시 호출·가림/복원·
사내 답변·임베딩·사전 재적재가 동작하는지 본다. 모델 품질은 demo_run/accept_run 이 보고, 여기서는 서비스 배관만 본다.

사용: .venv\\Scripts\\python.exe src\\tools\\server_check.py [--port 8010] [--no-llm] [--keep]
  --no-llm  /analyze 를 use_llm=false 로만 (Ollama 없이 배관 점검)
  --keep    끝나도 서버를 끄지 않음 (키는 결과 파일에 적힌다)
결과: src/results/server_check_<stamp>.md (+ 서버 로그 .log)
"""
import argparse
import json
import os
import secrets
import subprocess
import sys
import threading
import time
import urllib.error
import urllib.request
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from common import RESULTS, ROOT, find_all, load_samples, utf8_stdout  # noqa: E402
from detect import detect  # noqa: E402
from extract import extract_pdf  # noqa: E402

DEMO = ROOT / "data" / "demo" / "demo_docs_v1.jsonl"
ACCEPT = ROOT / "data" / "accept" / "TEST-01.json"
PROJECT = ROOT.parent


class Client:
    def __init__(self, base: str, key: str):
        self.base, self.key = base, key

    def call(self, method: str, path: str, body=None, key="default", timeout=600):
        headers = {"Content-Type": "application/json"}
        k = self.key if key == "default" else key
        if k:
            headers["X-API-Key"] = k
        data = json.dumps(body, ensure_ascii=False).encode("utf-8") if body is not None else None
        req = urllib.request.Request(self.base + path, data=data, headers=headers, method=method)
        t0 = time.perf_counter()
        try:
            with urllib.request.urlopen(req, timeout=timeout) as r:
                return r.status, json.loads(r.read().decode("utf-8")), time.perf_counter() - t0
        except urllib.error.HTTPError as e:
            raw = e.read().decode("utf-8", "replace")
            try:
                payload = json.loads(raw)
            except json.JSONDecodeError:
                payload = {"raw": raw[:300]}
            return e.code, payload, time.perf_counter() - t0


def wait_health(client: Client, proc, limit_s=180):
    t0 = time.perf_counter()
    while time.perf_counter() - t0 < limit_s:
        if proc.poll() is not None:
            raise RuntimeError(f"서버가 먼저 종료됨 (코드 {proc.returncode})")
        try:
            st, body, _ = client.call("GET", "/health", key=None, timeout=3)
            if st == 200 and body.get("ok"):
                return round(time.perf_counter() - t0, 1)
        except (urllib.error.URLError, OSError, TimeoutError):
            pass
        time.sleep(0.5)
    raise TimeoutError("서버 /health 응답 없음")


def key_set(spans):
    return {(s["start"], s["end"], s["label"]) for s in spans}


def main():
    utf8_stdout()
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", type=int, default=8010)
    ap.add_argument("--no-llm", action="store_true")
    ap.add_argument("--keep", action="store_true")
    ap.add_argument("--external", action="store_true", help="/answer_external 도 호출 (Anthropic 비용 발생, ANTHROPIC_API_KEY 필요)")
    a = ap.parse_args()

    stamp = datetime.now().strftime("%Y%m%d_%H%M")
    RESULTS.mkdir(exist_ok=True)
    out_md = RESULTS / f"server_check_{stamp}.md"
    out_log = RESULTS / f"server_check_{stamp}.log"
    key = secrets.token_urlsafe(16)
    base = f"http://127.0.0.1:{a.port}"
    checks, notes = [], []

    def check(name, ok, detail=""):
        checks.append({"name": name, "ok": bool(ok), "detail": detail})
        print(f"  {'O' if ok else 'X'} {name}" + (f" · {detail}" if detail else ""), flush=True)

    env = dict(os.environ)
    env.update({"MODEL_API_KEYS": key, "MODEL_WARM_OLLAMA": "0", "PYTHONIOENCODING": "utf-8"})
    logf = open(out_log, "w", encoding="utf-8")
    proc = subprocess.Popen([sys.executable, str(ROOT / "server.py"), "--host", "127.0.0.1", "--port", str(a.port)],
                            cwd=str(ROOT), env=env, stdout=logf, stderr=subprocess.STDOUT)
    client = Client(base, key)
    try:
        boot = wait_health(client, proc)
        print(f"서버 기동 {boot}s (NER 로딩 포함) · 포트 {a.port}", flush=True)

        # 1. 인증
        st_none, _, _ = client.call("GET", "/status", key=None)
        st_bad, _, _ = client.call("GET", "/status", key="wrong-key")
        st_ok, status, _ = client.call("GET", "/status")
        check("인증: 키 없음 401 · 틀린 키 401 · 맞는 키 200", st_none == 401 and st_bad == 401 and st_ok == 200,
              f"{st_none}/{st_bad}/{st_ok}")
        st_h, _, _ = client.call("GET", "/health", key=None)
        check("/health 는 키 없이 200", st_h == 200)
        loaded = [m["name"] for m in status.get("ollama", {}).get("loaded", [])] if st_ok == 200 else []
        notes.append(f"Ollama 응답 {status.get('ollama', {}).get('ok')} · 상주 모델 {loaded or '-'} · NER {status.get('ner_ready')} · 사전 {status.get('dict')}")

        # 2. 즉시 탐지 = 직접 호출
        rows = load_samples(DEMO)
        same, inst_ms = 0, []
        for r in rows:
            st, body, _ = client.call("POST", "/detect/instant", {"text": r["text"], "request_id": r["id"]})
            direct = detect(r["text"], use_llm=False)
            ok = st == 200 and key_set(body["spans"]) == {(s.start, s.end, s.label) for s in direct["spans"]}
            same += ok
            inst_ms.append(body["timing"]["total_ms"] if st == 200 else None)
        check(f"즉시 탐지 서버 = 직접 호출 ({same}/{len(rows)})", same == len(rows), f"서버 처리 {inst_ms} ms")

        # 3. 입력 검증
        st_empty, _, _ = client.call("POST", "/detect/instant", {"text": "   "})
        st_both, _, _ = client.call("POST", "/detect/instant", {"text": "a", "body": "b"})
        check("빈 글·text+body 동시는 422", st_empty == 422 and st_both == 422, f"{st_empty}/{st_both}")

        # 4. /analyze 시연 6건
        demo, bodies = [], {}
        use_llm = not a.no_llm
        for r in rows:
            st, body, secs = client.call("POST", "/analyze", {"text": r["text"], "request_id": r["id"], "use_llm": use_llm})
            if st != 200:
                demo.append({"id": r["id"], "expected": r["route"], "action": f"HTTP {st}", "ok": False, "restore": False})
                continue
            bodies[r["id"]] = body
            st_r, rest, _ = client.call("POST", "/restore", {"answer": body["mask"]["masked"], "mapping": body["mask"]["mapping"]})
            restored_ok = st_r == 200 and rest["restored"] == r["text"] and not rest["unresolved"]
            demo.append({"id": r["id"], "expected": r["route"], "action": body["decision"]["action"], "ok": body["decision"]["action"] == r["route"],
                         "approval": body["decision"]["needs_approval"], "mode": body["mode"], "spans": len(body["spans"]),
                         "masked": len(body["mask"]["entries"]), "restore": restored_ok, "total_s": body["timing"]["total_s"],
                         "llm_s": body["timing"].get("llm_total_s"), "route_s": body["timing"].get("route_s"), "wall_s": round(secs, 2),
                         "warnings": len(body["warnings"])})
        n_ok = sum(1 for d in demo if d["ok"])
        n_rest = sum(1 for d in demo if d.get("restore"))
        check(f"/analyze 결정 = 기대 경로 ({n_ok}/{len(demo)})", n_ok == len(demo), "; ".join(f"{d['id']} {d['expected']}→{d['action']}" for d in demo if not d["ok"]))
        check(f"가림→/restore 원문 일치 ({n_rest}/{len(demo)})", n_rest == len(demo))
        modes = {d.get("mode") for d in demo}
        check("mode 가 full (30B·tev1 모두 동작)" if use_llm else "mode 가 instant_only", modes == ({"full"} if use_llm else {"instant_only"}), str(modes))

        # 5. instant_only 모드
        d3 = next(r for r in rows if r["id"] == "D3")
        st, body, _ = client.call("POST", "/analyze", {"text": d3["text"], "use_llm": False})
        check("use_llm=false → mode instant_only, 라우팅은 수행", st == 200 and body["mode"] == "instant_only" and body["route"] is not None,
              f"action={body.get('decision', {}).get('action')} route={body.get('route', {}) and body['route'].get('choice')}")

        # 6. 동시 호출 2건
        if use_llm:
            d6 = next(r for r in rows if r["id"] == "D6")
            results = {}

            def worker(name, text):
                results[name] = client.call("POST", "/analyze", {"text": text, "request_id": name})

            t0 = time.perf_counter()
            ths = [threading.Thread(target=worker, args=(n, t)) for n, t in (("D3", d3["text"]), ("D6", d6["text"]))]
            [t.start() for t in ths]; [t.join() for t in ths]
            wall = round(time.perf_counter() - t0, 2)
            ok = all(v[0] == 200 for v in results.values())
            each = {k: v[1]["timing"]["total_s"] for k, v in results.items() if v[0] == 200}
            check("동시 /analyze 2건 모두 200 (30B 는 직렬)", ok, f"벽시계 {wall}s · 각 {each}")

        # 7. TEST-01 (instruction + body 형식)
        if ACCEPT.exists():
            spec = json.loads(ACCEPT.read_text(encoding="utf-8"))
            pdf = PROJECT / spec["pdf"]
            if pdf.exists():
                ex = extract_pdf(pdf)
                st, body, secs = client.call("POST", "/analyze", {"instruction": spec["instruction"], "body": ex["text"], "request_id": "TEST-01",
                                                                  "doc_name": pdf.name, "use_llm": use_llm})
                if st == 200:
                    text = spec["instruction"].strip() + "\n\n" + ex["text"]
                    check("TEST-01 body_offset = 요청문 길이 + 2", body["body_offset"] == len(spec["instruction"].strip()) + 2, str(body["body_offset"]))
                    masked_off = body["mask"]["masked"]
                    remaining = [(v["text"], len(find_all(masked_off, v["text"]))) for v in spec["tier1"] if find_all(text, v["text"])]
                    left = [f"{t}({n})" for t, n in remaining if n]
                    check(f"TEST-01 1등급 값 가린 본문에 남음 0 (사전 없음, {len(remaining)}값)", not left, ", ".join(left))
                    names_off = all(len(find_all(masked_off, v["text"])) == len(find_all(text, v["text"])) for v in spec["tier2"])
                    st_m, m_on, _ = client.call("POST", "/mask", {"text": text, "spans": body["spans"], "policy": {"mask_person": True}})
                    names_on = st_m == 200 and all(len(find_all(m_on["masked"], v["text"])) == 0 for v in spec["tier2"])
                    keep_ok = st_m == 200 and all(len(find_all(m_on["masked"], k)) == len(find_all(text, k)) for k in spec.get("keep", []))
                    check("TEST-01 이름 토글 끔: 이름 유지 · 켬(/mask): 이름만 가림 · 유지 항목 보존", names_off and names_on and keep_ok,
                          f"끔 {names_off} 켬 {names_on} 유지 {keep_ok}")
                    notes.append(f"TEST-01: {len(ex['pages'])}쪽 {len(text):,}자 · 결정 {body['decision']['action']} · 구간 {len(body['spans'])} · "
                                 f"조각 {body['timing'].get('chunks')} · 30B {body['timing'].get('llm_total_s')}s · 전체 {body['timing']['total_s']}s · mode {body['mode']}")
                else:
                    check("TEST-01 /analyze 200", False, f"HTTP {st} {str(body)[:200]}")
            else:
                notes.append(f"TEST-01 PDF 없음: {pdf}")

        # 8. 사내 답변
        if use_llm:
            d1 = rows[0]
            st, body, secs = client.call("POST", "/answer_local", {"text": d1["text"], "request_id": "D1", "max_tokens": 300})
            check("/answer_local 답변 생성", st == 200 and body.get("answer", "").strip() != "",
                  f"{round(secs, 1)}s · 출력 {body.get('eval_tokens')}토큰 · {body.get('done_reason')}" if st == 200 else f"HTTP {st} {str(body)[:150]}")

        # 8b. 외부 호출 (선택, 비용 발생)
        if a.external and "D3" in bodies:
            if not os.environ.get("ANTHROPIC_API_KEY"):
                check("/answer_external", False, "ANTHROPIC_API_KEY 없음 (서버 프로세스 환경)")
            else:
                mk = bodies["D3"]["mask"]
                st, body, secs = client.call("POST", "/answer_external", {"masked": mk["masked"], "mapping": mk["mapping"], "request_id": "D3"})
                ok = st == 200 and body.get("stop_reason") == "end_turn" and not body.get("unresolved")
                check("/answer_external D3 (가림 본문 → 외부 → 복원)", ok,
                      f"{body.get('served_by')} · 자리표 {body.get('placeholders')} · 토큰 {body.get('usage', {}).get('input_tokens')}/{body.get('usage', {}).get('output_tokens')} "
                      f"· ${body.get('cost_usd')} · {round(secs, 1)}s" if st == 200 else f"HTTP {st} {str(body)[:150]}")
            st, body, _ = client.call("POST", "/answer_external", {"masked": "x", "mapping": {}, "text": "y", "spans": []})
            st2, _, _ = client.call("POST", "/answer_external", {"masked": "x", "mapping": {}, "text": "y"})
            check("/answer_external 두 형식 동시·섞어 보내기는 422", st == 422 and st2 == 422, f"{st}/{st2}")
        else:
            st, body, _ = client.call("POST", "/answer_external", {"masked": "[[ORG_1]] 안녕", "mapping": {"[[ORG_1]]": "안녕"}})
            check("/answer_external 유출 검사 409 (원문 값이 가림 본문에 남음)", st == 409 or st == 503, f"{st} {body.get('detail', '')[:60]}")

        # 9. 임베딩
        st, body, secs = client.call("POST", "/embed", {"texts": [rows[0]["text"], d3["text"]]})
        check("/embed 2건 → 1024차원", st == 200 and body.get("dim") == 1024 and len(body.get("embeddings", [])) == 2,
              f"{round(secs, 2)}s dim={body.get('dim')}" if st == 200 else f"HTTP {st} {str(body)[:150]}")

        # 10. 사전 재적재 (파일 쓰기 없이 다시 읽기만)
        st, body, _ = client.call("POST", "/dict/reload", {})
        check("/dict/reload (다시 읽기) 200", st == 200 and body.get("ok") and not body.get("written"), str(body.get("terms")))

        # 11. /mask 입력 검증
        st, _, _ = client.call("POST", "/mask", {"text": "짧은 글", "spans": [{"start": 0, "end": 99, "label": "company"}]})
        check("/mask 글 밖 구간 422", st == 422, str(st))

    finally:
        st, status2, _ = client.call("GET", "/status") if proc.poll() is None else (0, {}, 0)
        if not a.keep:
            proc.terminate()
            try:
                proc.wait(timeout=15)
            except subprocess.TimeoutExpired:
                proc.kill()
        logf.close()

    n_ok = sum(1 for c in checks if c["ok"])
    md = [f"# 모델 서비스 점검 · {stamp}", "",
          f"server.py 를 127.0.0.1:{a.port} 에 띄우고 HTTP 로 호출. 통과 {n_ok}/{len(checks)}" + (" · use_llm=false" if a.no_llm else ""), ""]
    md += ["| 점검 | 결과 | 비고 |", "|---|---|---|"]
    md += [f"| {c['name']} | {'O' if c['ok'] else '✗'} | {c['detail'] or '-'} |" for c in checks]
    if demo:
        md += ["", "## 시연 6건 /analyze", "", "| 문서 | 기대 | 결정 | 승인 | mode | 구간 | 가림 | 복원 | 전체 s | 30B s | tev1 s | 왕복 s | 경고 |", "|---|---|---|---|---|---|---|---|---|---|---|---|---|"]
        for d in demo:
            md.append(f"| {d['id']} | {d['expected']} | {d['action']}{'' if d['ok'] else ' ✗'} | {d.get('approval', '-')} | {d.get('mode', '-')} | {d.get('spans', '-')} | "
                      f"{d.get('masked', '-')} | {'O' if d.get('restore') else '✗'} | {d.get('total_s', '-')} | {d.get('llm_s', '-')} | {d.get('route_s', '-')} | {d.get('wall_s', '-')} | {d.get('warnings', '-')} |")
    md += ["", "## 메모", ""] + [f"- {n}" for n in notes]
    if st == 200:
        md.append(f"- 종료 시점 서버: 요청 {status2.get('requests')} · 오류 {status2.get('errors')} · analyze {status2.get('analyze')} · 상주 {[m['name'] for m in status2.get('ollama', {}).get('loaded', [])]}")
    md.append(f"- 서버 로그: {out_log.name}" + (f" · 서버 유지 중, 키 {key}" if a.keep else ""))
    out_md.write_text("\n".join(md) + "\n", encoding="utf-8")
    print(f"통과 {n_ok}/{len(checks)} · 결과: {out_md}")


if __name__ == "__main__":
    main()
