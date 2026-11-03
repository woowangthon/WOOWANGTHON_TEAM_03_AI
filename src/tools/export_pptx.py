"""PowerPoint COM으로 .pptx를 슬라이드별 PNG와 PDF로 내보낸다 (시각 QA와 PDF 저장용).

사용: python src/tools/export_pptx.py "덱.pptx" "png출력폴더" ["pdf경로"]
"""
import sys
from pathlib import Path

import win32com.client


def main(pptx: Path, png_dir: Path, pdf: Path | None):
    pptx = pptx.resolve()
    png_dir = png_dir.resolve()
    png_dir.mkdir(parents=True, exist_ok=True)
    app = win32com.client.Dispatch("PowerPoint.Application")
    pres = app.Presentations.Open(str(pptx), ReadOnly=True, Untitled=False, WithWindow=False)
    try:
        for i, slide in enumerate(pres.Slides, start=1):
            out = png_dir / f"slide-{i}.png"
            slide.Export(str(out), "PNG", 1920, 1080)
            print("png", out)
        if pdf:
            pres.SaveAs(str(pdf.resolve()), 32)  # ppSaveAsPDF
            print("pdf", pdf.resolve())
    finally:
        pres.Close()
        app.Quit()


if __name__ == "__main__":
    main(Path(sys.argv[1]), Path(sys.argv[2]), Path(sys.argv[3]) if len(sys.argv) > 3 else None)
