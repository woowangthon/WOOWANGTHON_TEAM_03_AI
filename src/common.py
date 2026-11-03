"""공통 유틸: 경로, Ollama 호출, 구간(span) 자료형, 통계."""
import json
import sys
import time
import urllib.error
import urllib.request
from dataclasses import dataclass, field, asdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent
DATA = ROOT / "data"
DICT_DIR = DATA / "dict"
RESULTS = ROOT / "results"

# 'localhost'를 쓰면 Windows에서 IPv6(::1) 먼저 시도하다 호출마다 약 2초가 붙는다. 반드시 127.0.0.1.
OLLAMA = "http://127.0.0.1:11434"
LLM_MODEL = "qwen3:30b-a3b-instruct-2507-q4_K_M"
DECISION_MODEL = "tev1-cpu"
KEEP_ALIVE = "30m"

LABELS = ["company", "project", "doc_no", "price", "person", "contact", "biz_no", "other"]
LABEL_KO = {
    "company": "회사명", "project": "사업명", "doc_no": "식별번호", "price": "금액",
    "person": "사람", "contact": "연락처", "biz_no": "사업자/주민번호", "other": "기타",
}


def utf8_stdout():
    """Windows 콘솔(cp949)에서 한글이 깨지지 않게."""
    for s in (sys.stdout, sys.stderr):
        try:
            s.reconfigure(encoding="utf-8")
        except Exception:
            pass


@dataclass
class Span:
    start: int
    end: int
    text: str
    label: str
    sources: list = field(default_factory=list)

    def overlap(self, other) -> int:
        return max(0, min(self.end, other.end) - max(self.start, other.start))

    def to_dict(self):
        return asdict(self)


def post_json(path: str, body: dict, timeout: float = 600):
    """Ollama에 JSON POST. (응답 dict, 소요 초) 반환."""
    data = json.dumps(body, ensure_ascii=False).encode("utf-8")
    req = urllib.request.Request(OLLAMA + path, data=data,
                                 headers={"Content-Type": "application/json"}, method="POST")
    t0 = time.perf_counter()
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            out = json.loads(r.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        raise RuntimeError(f"{path} HTTP {e.code}: {e.read().decode('utf-8', 'replace')[:500]}")
    return out, time.perf_counter() - t0


def find_all(text: str, sub: str):
    """sub가 text에 나오는 모든 (start, end)."""
    out, i = [], 0
    if not sub:
        return out
    while True:
        j = text.find(sub, i)
        if j < 0:
            break
        out.append((j, j + len(sub)))
        i = j + 1
    return out


def percentile(values, p: float):
    """nearest-rank 백분위. 값이 없으면 None."""
    if not values:
        return None
    vals = sorted(values)
    k = max(1, int(round(p / 100 * len(vals) + 0.5)))
    return vals[min(k, len(vals)) - 1]


def load_samples(path: Path):
    rows = []
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows
