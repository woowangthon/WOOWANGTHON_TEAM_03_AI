"""공통 유틸: 경로, Ollama 호출, 구간(span) 자료형, 통계."""
import json
import os
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
# 요청마다 Ollama 에 넘기는 keep_alive. 요청 값이 서버 환경변수 OLLAMA_KEEP_ALIVE 보다 우선하므로, 상시 가동(ops/)에서는
# MODEL_KEEP_ALIVE=-1 로 세 모델을 내리지 않는다(내려가면 30B 첫 호출이 14~17초). 숫자는 초(음수 = 무기한), 문자열은 "30m" 같은 기간.
_keep_alive = os.environ.get("MODEL_KEEP_ALIVE", "30m").strip() or "30m"
KEEP_ALIVE = int(_keep_alive) if _keep_alive.lstrip("-").isdigit() else _keep_alive

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
