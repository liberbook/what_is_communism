#!/usr/bin/env python3
"""Build check (no AI): verify the outputs of build_book.py for each edition.

  errors    a missing output (PDF A4, print PDF, booklet, EPUB, FB2, HTML, MD);
            LaTeX errors when compiling <dir>/main.tex; a section title missing
            from the PDF text; Cyrillic letters in a non-Cyrillic edition;
            the language of the EPUB, FB2 or HTML differing from languages.toml;
            fewer EPUB footnotes than \\footnote in the parts
  warnings  overfull boxes (text running into the margin); page counts that
            differ from the source edition by more than 30 %

Needs pdflatex and pdftotext (poppler-utils). Run after ./build.sh.
Exit code 1 when any error is found.

Usage: python3 tools/checks/build.py [codes ...]
"""
from __future__ import annotations

import argparse
import re
import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import edlib  # noqa: E402
from structure import CYRILLIC, CYRILLIC_LANGS  # noqa: E402


def pages(pdf: Path) -> int:
    out = subprocess.run(["pdfinfo", str(pdf)], capture_output=True, text=True).stdout
    m = re.search(r"^Pages:\s+(\d+)", out, re.M)
    return int(m.group(1)) if m else 0


def norm(s: str) -> str:
    s = re.sub(r"\\[a-zA-Z]+\{?|[{}]", "", s)
    # T2A fonts store Ukrainian і/ї as Latin i/ï; compare without that difference
    s = s.translate(str.maketrans({"і": "i", "І": "I", "ї": "ï", "Ї": "Ï", "’": "'", "ʼ": "'", "`": "'"}))
    return re.sub(r"\s+", " ", s).strip().lower()


def latex_log(ed: edlib.Edition) -> tuple[int, int, list[str]]:
    with tempfile.TemporaryDirectory() as tmp:
        subprocess.run(["pdflatex", "-interaction=nonstopmode", f"-output-directory={tmp}", "main.tex"],
                       cwd=ed.src, capture_output=True)
        log = (Path(tmp) / "main.log").read_text(encoding="utf-8", errors="replace")
    errs = re.findall(r"^! (.*)$", log, re.M)
    return len(errs), len(re.findall(r"^Overfull \\hbox", log, re.M)), errs[:3]


def check(ed: edlib.Edition, cfg: edlib.Config) -> tuple[list[str], list[str]]:
    E: list[str] = []
    W: list[str] = []
    out = edlib.ROOT / "out" / ed.dir
    b = ed.basename
    files = {"pdf": out / "pdf" / f"{b}.pdf", "print": out / "print" / f"{b}_print.pdf",
             "booklet": out / "print" / f"{b}_booklet_a4.pdf", "epub": out / f"{b}.epub",
             "fb2": out / f"{b}.fb2", "html": out / f"{b}.html", "md": out / f"{b}.md"}
    for k, p in files.items():
        if not p.exists() or p.stat().st_size == 0:
            E.append(f"missing output {edlib.rel(p)}")
    if E:
        return E, W
    n_err, n_over, first = latex_log(ed)
    if n_err:
        E.append(f"{n_err} LaTeX error(s), e.g. {first}")
    if n_over:
        W.append(f"{n_over} overfull box(es) in the A4 PDF")
    text = subprocess.run(["pdftotext", str(files["pdf"]), "-"], capture_output=True, text=True).stdout
    flat = norm(text)
    parts = [edlib.read_part(p) for p in ed.part_paths()]
    for p in parts:
        if norm(p.title) not in flat:
            E.append(f"section title not found in the PDF: {p.title!r}")
    if ed.lang not in CYRILLIC_LANGS and CYRILLIC.search(text):
        sample = sorted(set(re.findall(r"\S*[\u0400-\u04FF]+\S*", text)))[:5]
        E.append(f"Cyrillic letters in the PDF: {sample}")
    with zipfile.ZipFile(files["epub"]) as z:
        opf = z.read(next(n for n in z.namelist() if n.endswith(".opf"))).decode("utf-8")
        body = "".join(z.read(n).decode("utf-8", "replace") for n in z.namelist() if n.endswith((".xhtml", ".html")))
    m = re.search(r"<dc:language[^>]*>([^<]+)<", opf)
    if not m or m.group(1).split("-")[0] != ed.lang.split("-")[0]:
        E.append(f"EPUB language {m.group(1) if m else None!r}, expected {ed.lang!r}")
    n_fn = sum(len(p.footnotes) for p in parts)
    n_ref = len(re.findall(r'doc-noteref|class="footnote-ref"', body))
    if n_ref < n_fn:
        E.append(f"EPUB has {n_ref} footnote references, the parts have {n_fn} footnotes")
    fb2 = files["fb2"].read_text(encoding="utf-8", errors="replace")
    m = re.search(r"<lang>([^<]+)</lang>", fb2)
    if not m or m.group(1) != ed.lang:
        E.append(f"FB2 language {m.group(1) if m else None!r}, expected {ed.lang!r}")
    m = re.search(r'<html[^>]*\blang="([^"]+)"', files["html"].read_text(encoding="utf-8", errors="replace"))
    if not m or m.group(1) != ed.lang:
        E.append(f"HTML language {m.group(1) if m else None!r}, expected {ed.lang!r}")
    src_pdf = edlib.ROOT / "out" / cfg.source.dir / "pdf" / f"{cfg.source.basename}.pdf"
    n, n0 = pages(files["pdf"]), pages(src_pdf) if src_pdf.exists() else 0
    if n0 and abs(n - n0) / n0 > 0.3:
        W.append(f"{n} pages, the source edition has {n0}")
    W.append(f"info: {n} pages A4, {pages(files['print'])} pages A5, {pages(files['booklet'])} booklet sheets")
    return E, W


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("codes", nargs="*", help="editions (default: all)")
    args = ap.parse_args()
    cfg = edlib.load_config()
    eds = [cfg.edition(c) for c in args.codes] if args.codes else cfg.editions
    n_err = 0
    for ed in eds:
        errs, warns = check(ed, cfg)
        print(f"[build] {ed.code}: {'OK' if not errs else f'{len(errs)} error(s)'}")
        for e in errs:
            print(f"  ERROR   {e}")
        for w in warns:
            print(f"  {'' if w.startswith('info') else 'warning '}{w}")
        n_err += len(errs)
    sys.exit(1 if n_err else 0)


if __name__ == "__main__":
    main()
