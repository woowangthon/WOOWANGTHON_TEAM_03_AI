"""PDF → 글자. 모델은 글자만 받으므로 파일 입력은 여기서 글자로 바꾼다 (11-01 설계. 백엔드가 직접 뽑아도 같은 규칙).

extract_pdf(data) -> {"text": str, "pages": [{"page", "start", "end"}], "chars": int, "warnings": [str], "ok": bool}
- 글자는 고치지 않는다(전각·대시 정리는 즉시 탐지의 정규화가 한다). 줄바꿈 유지, 쪽 사이 빈 줄 하나, 본문에 쪽 표식을 넣지 않는다.
- 읽기 순서(위→아래, 왼→오른)로 정렬. 글자가 거의 없으면 스캔본 경고(OCR 미지원), 쪽수·글자 수 상한 초과는 경고 + ok=False.
- 구간 위치는 이 text 기준 글자 번호다. 모델에 넘기는 문자열과 화면에 그리는 문자열은 이것과 같아야 한다.
"""
from pathlib import Path

import pymupdf

MAX_PAGES = 50
MAX_CHARS = 60_000
MIN_CHARS = 50
PAGE_SEP = "\n\n"


def extract_pdf(data, max_pages: int = MAX_PAGES, max_chars: int = MAX_CHARS) -> dict:
    """data: bytes 또는 파일 경로."""
    warnings = []
    doc = pymupdf.open(str(data)) if isinstance(data, (str, Path)) else pymupdf.open(stream=data, filetype="pdf")
    with doc:
        if doc.needs_pass:
            return {"text": "", "pages": [], "chars": 0, "warnings": ["암호가 걸린 PDF는 지원하지 않음"], "ok": False}
        if doc.page_count > max_pages:
            warnings.append(f"{doc.page_count}쪽 중 앞 {max_pages}쪽만 추출")
        parts, pages, pos = [], [], 0
        for i, page in enumerate(doc):
            if i >= max_pages:
                break
            if i:
                parts.append(PAGE_SEP)
                pos += len(PAGE_SEP)
            t = page.get_text("text", sort=True)
            pages.append({"page": i + 1, "start": pos, "end": pos + len(t)})
            parts.append(t)
            pos += len(t)
    text = "".join(parts)
    ok = True
    if len(text.strip()) < MIN_CHARS:
        warnings.append("글자가 거의 없음: 스캔본이거나 이미지 PDF로 보임(OCR 미지원)")
        ok = False
    if len(text) > max_chars:
        warnings.append(f"글자 수 {len(text):,}자가 상한 {max_chars:,}자를 넘음. 나눠서 요청해야 함")
        ok = False
    return {"text": text, "pages": pages, "chars": len(text), "warnings": warnings, "ok": ok}


if __name__ == "__main__":
    import sys
    from common import utf8_stdout
    utf8_stdout()
    r = extract_pdf(sys.argv[1])
    print(f"{len(r['pages'])}쪽 {r['chars']:,}자 ok={r['ok']} 경고={r['warnings']}")
    print(r["text"][:1500])
