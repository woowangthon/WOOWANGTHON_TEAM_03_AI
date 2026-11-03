"""md → HTML → PDF (Word COM). 팀 공유 문서는 md와 PDF를 같이 저장한다.

사용: python src/tools/md2pdf.py "문서.md" ["출력.pdf"]
"""
import sys
import tempfile
from pathlib import Path

import markdown
import win32com.client

CSS = """
body { font-family: 'Malgun Gothic', sans-serif; font-size: 10.5pt; line-height: 1.5; }
h1 { font-size: 18pt; } h2 { font-size: 14pt; margin-top: 18pt; } h3 { font-size: 12pt; margin-top: 12pt; }
table { border-collapse: collapse; width: 100%; font-size: 9.5pt; }
th, td { border: 1px solid #999; padding: 4px 6px; vertical-align: top; }
th { background: #eef1f4; }
code { font-family: Consolas, monospace; font-size: 9.5pt; }
"""


def main(md_path: Path, pdf_path: Path | None):
    md_path = md_path.resolve()
    pdf_path = (pdf_path or md_path.with_suffix(".pdf")).resolve()
    html = markdown.markdown(md_path.read_text(encoding="utf-8"), extensions=["tables", "fenced_code"])
    doc = f"<html><head><meta charset='utf-8'><style>{CSS}</style></head><body>{html}</body></html>"
    tmp = Path(tempfile.gettempdir()) / (md_path.stem + ".html")
    tmp.write_text(doc, encoding="utf-8")
    word = win32com.client.Dispatch("Word.Application")
    word.Visible = False
    d = word.Documents.Open(str(tmp), ReadOnly=True, ConfirmConversions=False, Encoding=65001)
    try:
        d.SaveAs2(str(pdf_path), FileFormat=17)  # wdFormatPDF
    finally:
        d.Close(False)
        word.Quit()
    print("pdf", pdf_path)


if __name__ == "__main__":
    main(Path(sys.argv[1]), Path(sys.argv[2]) if len(sys.argv) > 2 else None)
