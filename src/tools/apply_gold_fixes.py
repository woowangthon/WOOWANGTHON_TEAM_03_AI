"""정답 수정 적용 (2026-10-30). fixes.json의 판정을 평가 세트 jsonl에 반영하고 변경 로그 md를 쓴다.

fixes.json 형식:
{
  "files": {"후보 40": "src/data/candidates/samples_clean_....jsonl", ...},
  "changes": [
    {"set": "후보 40", "id": "C02-1", "op": "add", "text": "김민수", "label": "person", "reason": "..."},
    {"set": "...", "id": "...", "op": "delete", "text": "Project Kestrel", "reason": "..."},
    {"set": "...", "id": "...", "op": "relabel", "text": "Lot 8832-19", "label": "doc_no", "reason": "..."},
    {"set": "...", "id": "...", "op": "retext", "text": "프로젝트 ID: HS-2024-087", "new_text": "HS-2024-087", "label": "doc_no", "reason": "..."},
    {"set": "...", "id": "...", "op": "keep", "text": "...", "reason": "..."}   # 로그에만 남김
  ]
}
사용: python src/tools/apply_gold_fixes.py <fixes.json> <변경 로그 md 경로>
원본은 같은 폴더에 <이름>_before_review_<stamp>.jsonl 로 복사해 둔다.
"""
import json
import shutil
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))
from common import utf8_stdout  # noqa: E402

utf8_stdout()
fixes = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
log_path = Path(sys.argv[2])
stamp = datetime.now().strftime("%Y%m%d_%H%M")

OP_KO = {"add": "정답 추가", "delete": "정답 삭제", "relabel": "라벨 교정", "retext": "표기 수정", "keep": "정답 유지"}
applied = []
problems = []

for set_name, rel in fixes["files"].items():
    path = ROOT / rel
    rows = [json.loads(l) for l in path.read_text(encoding="utf-8").splitlines() if l.strip()]
    by_id = {r["id"]: r for r in rows}
    changes = [c for c in fixes["changes"] if c["set"] == set_name and c["op"] != "keep"]
    if not changes:
        continue
    shutil.copy(path, path.with_name(f"{path.stem}_before_review_{stamp}.jsonl"))
    for c in changes:
        r = by_id.get(c["id"])
        if r is None:
            problems.append(f"{set_name} {c['id']}: 항목 없음")
            continue
        spans = r.setdefault("spans", [])
        if c["op"] == "add":
            if c["text"] not in r["text"]:
                problems.append(f"{set_name} {c['id']}: 본문에 없음 '{c['text']}'")
                continue
            if any(s["text"] == c["text"] for s in spans):
                problems.append(f"{set_name} {c['id']}: 이미 있음 '{c['text']}'")
                continue
            spans.append({"text": c["text"], "label": c["label"]})
        elif c["op"] == "delete":
            before = len(spans)
            spans[:] = [s for s in spans if s["text"] != c["text"]]
            if len(spans) == before:
                problems.append(f"{set_name} {c['id']}: 삭제 대상 없음 '{c['text']}'")
                continue
        elif c["op"] == "relabel":
            hit = [s for s in spans if s["text"] == c["text"]]
            if not hit:
                problems.append(f"{set_name} {c['id']}: 라벨 교정 대상 없음 '{c['text']}'")
                continue
            for s in hit:
                s["label"] = c["label"]
        elif c["op"] == "retext":
            hit = [s for s in spans if s["text"] == c["text"]]
            if not hit or c["new_text"] not in r["text"]:
                problems.append(f"{set_name} {c['id']}: 표기 수정 실패 '{c['text']}' → '{c['new_text']}'")
                continue
            for s in hit:
                s["text"] = c["new_text"]
                if c.get("label"):
                    s["label"] = c["label"]
        r.setdefault("review", {}).setdefault("manual", []).append(f"{stamp} {OP_KO[c['op']]}: {c['text']}" + (f" → {c['new_text']}" if c.get("new_text") else "") + (f" ({c['label']})" if c.get("label") else ""))
        applied.append(c)
    path.write_text("\n".join(json.dumps(r, ensure_ascii=False) for r in rows) + "\n", encoding="utf-8")
    print(f"{set_name}: {len(changes)}건 적용 → {path.name}")

# 변경 로그 (이미 있으면 뒤에 덧붙인다)
if log_path.exists():
    md = [log_path.read_text(encoding="utf-8").rstrip(), "", f"## 추가 판정 ({datetime.now():%Y-%m-%d %H:%M})", "",
          "| # | 세트 | id | 판정 | 구간 | 라벨 | 이유 |", "|---|---|---|---|---|---|---|"]
else:
    md = [f"# 정답 검토 변경 로그 ({datetime.now():%Y-%m-%d})", "",
          "혼합 탐지기와 정답이 다른 54곳을 모델링이 기준표(회사명·사업명·식별번호·금액·사람·연락처·사업자번호는 구간, 날짜·수량·치수·공개 규격·직급은 제외, 사람은 이름만)로 판정했다. "
          "팀 확인용: 아무 행이나 10건을 골라 본문과 대조하면 된다. 원본 jsonl은 *_before_review_*.jsonl 로 남겨 두었다.", "",
          "| # | 세트 | id | 판정 | 구간 | 라벨 | 이유 |", "|---|---|---|---|---|---|---|"]
for i, c in enumerate(fixes["changes"], 1):
    span = c["text"].replace("\n", "⏎").replace("|", "\\|")
    if c.get("new_text"):
        span += " → " + c["new_text"]
    md.append(f"| {i} | {c['set']} | {c['id']} | {OP_KO[c['op']]} | `{span}` | {c.get('label', '')} | {c['reason']} |")
md.append("")
n_ops = {}
for c in fixes["changes"]:
    n_ops[OP_KO[c["op"]]] = n_ops.get(OP_KO[c["op"]], 0) + 1
md.append("집계: " + " · ".join(f"{k} {v}" for k, v in n_ops.items()))
if problems:
    md.append("\n적용 실패:\n" + "\n".join(f"- {p}" for p in problems))
log_path.write_text("\n".join(md), encoding="utf-8")
print(f"적용 {len(applied)}건, 실패 {len(problems)}건 → {log_path}")
for p in problems:
    print("!!", p)
