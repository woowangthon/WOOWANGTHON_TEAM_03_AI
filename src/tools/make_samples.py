"""프론트·백엔드 연동용 샘플 만들기: 서버를 띄워 시연 문서 D1~D6 를 실제로 돌리고 경로별 요청·응답 JSON 을 docs/samples/ 에 저장한다.
외부 호출(D3)과 사내 답변(D2)도 실제로 부르고, 30B·tev1 이 죽었을 때의 축소 응답(degraded)은 Ollama 주소를 막은 두 번째 서버로 만든다.
시연 문서 6건은 PDF 업로드 화면용으로 docs/samples/demo-pdf/ 에 PDF 로도 뽑는다 (Edge 인쇄, 없으면 Word).

사용: .venv\\Scripts\\python.exe src\\tools\\make_samples.py [--port 8016] [--no-external]
전제: Ollama 가 떠 있고, 외부 호출 샘플에는 환경변수 ANTHROPIC_API_KEY 가 필요하다 (약 $0.01).
"""
import argparse
import json
import os
import secrets
import subprocess
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from accept_run import md_to_pdf  # noqa: E402
from common import ROOT, load_samples, utf8_stdout  # noqa: E402
from server_check import Client, wait_health  # noqa: E402

DEMO = ROOT / "data" / "demo" / "demo_docs_v1.jsonl"
OUT = ROOT.parent / "docs" / "samples"
PDF_DIR = OUT / "demo-pdf"


def start_server(port: int, key: str, dead_ollama: bool, logf):
    env = dict(os.environ)
    env.update({"MODEL_API_KEYS": key, "MODEL_WARM_OLLAMA": "0", "PYTHONIOENCODING": "utf-8"})
    if dead_ollama:  # common.OLLAMA 를 닫힌 포트로 바꿔 30B·tev1 호출이 실패하게 한다 (NER·규칙·가림은 그대로)
        code = (f"import sys; sys.path.insert(0, r'{ROOT}'); import common; common.OLLAMA = 'http://127.0.0.1:9'; "
                f"import server, uvicorn; uvicorn.run(server.app, host='127.0.0.1', port={port}, log_level='warning')")
        cmd = [sys.executable, "-c", code]
    else:
        cmd = [sys.executable, str(ROOT / "server.py"), "--host", "127.0.0.1", "--port", str(port)]
    return subprocess.Popen(cmd, cwd=str(ROOT), env=env, stdout=logf, stderr=subprocess.STDOUT)


def save(name: str, request, response, status: int, note: str):
    path = OUT / f"{name}.json"
    path.write_text(json.dumps({"note": note, "http_status": status, "request": request, "response": response},
                               ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"  저장 {path.name} ({status})", flush=True)


def stop(proc):
    proc.terminate()
    try:
        proc.wait(timeout=15)
    except subprocess.TimeoutExpired:
        proc.kill()


def main():
    utf8_stdout()
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", type=int, default=8016)
    ap.add_argument("--no-external", action="store_true")
    a = ap.parse_args()
    OUT.mkdir(parents=True, exist_ok=True)
    PDF_DIR.mkdir(exist_ok=True)
    rows = {r["id"]: r for r in load_samples(DEMO)}
    key = secrets.token_urlsafe(12)
    logf = open(OUT / "_server.log", "w", encoding="utf-8")

    # 1. 정상 서버: 시연 6건 분석, 즉시 탐지, 가림 토글, 사내 답변, 외부 호출, 오류 응답
    proc = start_server(a.port, key, False, logf)
    client = Client(f"http://127.0.0.1:{a.port}", key)
    try:
        wait_health(client, proc)
        print("정상 서버 기동", flush=True)
        note = {"D1": "사내 처리 · 구간 없음 · 승인 카드 없음", "D2": "사내 강제 · 본문에 '대외비' 표기", "D3": "외부 전송 · 구간 있음 · 승인 카드 필요",
                "D4": "외부 전송 · 구간 없음 · 그대로 전송", "D5": "차단 · 통째 유출 요청", "D6": "외부 전송 + 지시 삽입 경고 · 승인 카드 필요"}
        analyzed = {}
        for rid, r in rows.items():
            req = {"text": r["text"], "request_id": f"sample-{rid}", "doc_name": f"{rid}.pdf", "policy": {"mask_person": False, "mask_company": True}}
            st, body, _ = client.call("POST", "/analyze", req)
            analyzed[rid] = body
            save(f"analyze_{rid}", req, body, st, f"{rid} {r['case']} — 기대 결정 {r['route']} — {note[rid]}")
        req = {"instruction": "아래 보고서를 영문으로 번역해 주세요.", "body": rows["D3"]["text"].split("\n\n", 1)[1], "request_id": "sample-D3-instant"}
        st, body, _ = client.call("POST", "/detect/instant", req)
        save("detect_instant_D3", req, body, st, "접수 즉시 1차 카드용. instruction + body 로 보내면 body_offset 이 돌아온다 (D3 본문만 body 로)")
        d3 = analyzed["D3"]
        req = {"text": rows["D3"]["text"], "spans": d3["spans"], "policy": {"mask_person": True}}
        st, body, _ = client.call("POST", "/mask", req)
        save("mask_D3_person_on", req, body, st, "승인 카드에서 '이름도 가리기' 토글을 켰을 때: /analyze 의 spans 를 그대로 다시 보낸다")
        released = [s for s in d3["spans"] if s["label"] != "price"]
        req = {"text": rows["D3"]["text"], "spans": released, "policy": {"mask_person": False}}
        st, body, _ = client.call("POST", "/mask", req)
        save("mask_D3_release_price", req, body, st, "1등급 구간 해제 예: 사람이 사유를 적고 금액 구간을 풀면, 그 구간을 뺀 spans 로 /mask 를 다시 부른다 (해제 기록은 백엔드 DB)")
        req = {"text": rows["D2"]["text"], "request_id": "sample-D2-local", "max_tokens": 600}
        st, body, _ = client.call("POST", "/answer_local", req)
        save("answer_local_D2", req, body, st, "사내 처리(4.1): 원문 그대로 집 PC 30B 가 답한다. 외부로 나가지 않는다")
        if not a.no_external and os.environ.get("ANTHROPIC_API_KEY"):
            req = {"masked": d3["mask"]["masked"], "mapping": d3["mask"]["mapping"], "request_id": "sample-D3-external"}
            st, body, _ = client.call("POST", "/answer_external", req)
            save("answer_external_D3", req, body, st, "외부 전송(4.2): 가림 본문만 Anthropic 에 보내고 answer(자리표 그대로)·restored(복원)·unresolved 를 받는다")
        else:
            print("  외부 호출 샘플 생략 (키 없음 또는 --no-external)", flush=True)
        req = {"text": rows["D3"]["text"], "request_id": "sample-D3-instant-only", "use_llm": False}
        st, body, _ = client.call("POST", "/analyze", req)
        save("analyze_D3_instant_only", req, body, st, "use_llm=false: 30B 없이 즉시 경로만. mode=instant_only")
        errors = {}
        st, body, _ = client.call("POST", "/analyze", {"text": "x"}, key="wrong-key")
        errors["401_wrong_key"] = {"http_status": st, "response": body}
        st, body, _ = client.call("POST", "/analyze", {"text": "a", "body": "b"})
        errors["422_text_and_body"] = {"http_status": st, "response": body}
        st, body, _ = client.call("POST", "/answer_external", {"masked": "본문 한빛에어로 [[ORG_1]]", "mapping": {"[[ORG_1]]": "한빛에어로"}})
        errors["409_leak_check"] = {"http_status": st, "response": body}
        (OUT / "errors.json").write_text(json.dumps(errors, ensure_ascii=False, indent=2), encoding="utf-8")
        print("  저장 errors.json", flush=True)
    finally:
        stop(proc)

    # 2. Ollama 가 죽은 서버: 축소 모드 응답
    proc = start_server(a.port + 1, key, True, logf)
    client = Client(f"http://127.0.0.1:{a.port + 1}", key)
    try:
        wait_health(client, proc)
        req = {"text": rows["D3"]["text"], "request_id": "sample-D3-degraded"}
        st, body, _ = client.call("POST", "/analyze", req)
        save("analyze_D3_degraded", req, body, st, "30B 와 tev1 호출이 모두 실패했을 때: mode=degraded, spans 는 즉시 경로만, route=null, 결정은 사내 폴백, warnings 에 사유")
    finally:
        stop(proc)
        logf.close()

    # 3. 시연 문서 PDF
    for rid, r in rows.items():
        md = PDF_DIR / f"{rid}.md"
        body = r["text"].split("\n\n", 1)
        md.write_text(f"# {rid} · {r['format']}\n\n" + body[-1].replace("\n", "  \n") + "\n", encoding="utf-8")
        md_to_pdf(md, PDF_DIR / f"{rid}.pdf")
        md.unlink()
        print(f"  PDF {rid}.pdf", flush=True)

    # 4. 안내 README
    lines = ["# 연동용 샘플 (2026-11-03, 집 PC 실측)", "",
             "서버(`src/server.py`)를 실제로 띄워 시연 문서로 만든 요청·응답이다. 각 json 은 `{note, http_status, request, response}` 꼴이고 "
             "`request` 를 그대로 보내면 같은 형식의 응답이 온다(30B 는 실행마다 구간이 ±1 흔들릴 수 있다). 문서는 전부 가상 데이터.", "",
             "| 파일 | 경로 | 내용 |", "|---|---|---|"]
    for p in sorted(OUT.glob("*.json")):
        if p.name == "errors.json":
            lines.append("| errors.json | /analyze, /answer_external | 401 키 오류, 422 입력 오류, 409 전송 직전 유출 검사 |")
            continue
        j = json.loads(p.read_text(encoding="utf-8"))
        path = p.stem.split("_")[0]
        route = {"analyze": "/analyze", "detect": "/detect/instant", "mask": "/mask", "answer": "/answer_local 또는 /answer_external"}.get(path, path)
        lines.append(f"| {p.name} | {route} | {j['note']} |")
    lines += ["", "## 시연 문서 D1~D6", "", "원문·기대 결정·정답 구간은 `src/data/demo/demo_docs_v1.jsonl`, 설명은 `docs/시연 문서 세트 v1 (2026-10-29).md`. "
              "PDF 업로드 화면용 파일은 `demo-pdf/D1.pdf` ~ `D6.pdf`(본문만, 요청 문장은 입력창에 따로 넣는다).", "",
              "| 문서 | 경우 | 요청 문장 | 기대 결정 | 카드 |", "|---|---|---|---|---|"]
    for rid, r in rows.items():
        instr = r["text"].split("\n\n", 1)[0].replace("|", "/")
        lines.append(f"| {rid} | {r['case']} | {instr} | {r['route']} | {r['card']} |")
    (OUT / "README.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"완료: {OUT}")


if __name__ == "__main__":
    main()
