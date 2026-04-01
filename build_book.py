#!/usr/bin/env python3
from __future__ import annotations

import html
import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent
OUT_ROOT = ROOT / "out"
MARKDOWN_IMAGE_SUFFIXES = {".jpg", ".jpeg", ".png", ".gif", ".webp", ".svg"}

CONFIGS = {
    "russian": {
        "src": ROOT / "russian",
        "title": "Что такое коммунизм?",
        "author": "Группа Энгельс",
        "lang": "ru",
        "basename": "chto_takoe_kommunizm",
    },
    "ukrainian": {
        "src": ROOT / "ukrainian",
        "title": "Що таке комунізм?",
        "author": "Група Енгельс",
        "lang": "uk",
        "basename": "shcho_take_komunizm",
    },
    "italiano": {
        "src": ROOT / "italiano",
        "title": "Che cos'è il comunismo?",
        "author": "Gruppo Engels",
        "lang": "it",
        "basename": "che_cose_il_comunismo",
    },
}

PRINT_PREAMBLE_PATCH = r"""
% ─── Print version: A5 page size, balanced margins ───────────────────────────
\geometry{
  paper=a5paper,
  top=1.8cm, bottom=1.8cm,
  inner=2.0cm, outer=1.5cm,
  twoside,
}
""".strip()


def run(cmd: list[str], cwd: Path | None = None) -> None:
    result = subprocess.run(cmd, cwd=cwd, capture_output=True)
    if result.returncode != 0:
        sys.stderr.write(result.stdout.decode("utf-8", errors="ignore"))
        sys.stderr.write(result.stderr.decode("utf-8", errors="ignore"))
        raise SystemExit(result.returncode)


def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def write_text(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def copy_markdown_assets(images_dir: Path, out_dir: Path) -> None:
    for asset in images_dir.iterdir():
        if asset.is_file() and asset.suffix.lower() in MARKDOWN_IMAGE_SUFFIXES:
            shutil.copy2(asset, out_dir / asset.name)


def inline_subfiles(main_tex: str, src_dir: Path) -> str:
    def repl(match: re.Match[str]) -> str:
        rel = match.group(1)
        part_path = src_dir / f"{rel}.tex"
        part = read_text(part_path)
        body = re.search(r"\\begin\{document\}(.*?)\\end\{document\}", part, re.DOTALL)
        return body.group(1).strip() if body else ""

    return re.sub(r"\\subfile\{([^}]+)\}", repl, main_tex)


def make_flat_tex(cfg: dict[str, object], out_dir: Path) -> Path:
    src_dir = cfg["src"]
    assert isinstance(src_dir, Path)
    main = read_text(src_dir / "main.tex")
    preamble = read_text(src_dir / "preamble.tex")
    flat = main.replace(r"\input{preamble}", preamble)
    flat = re.sub(r"\\begin\{document\}.*?(?=\\subfile\{)", r"\\begin{document}\n", flat, flags=re.DOTALL)
    flat = inline_subfiles(flat, src_dir)
    flat = re.sub(
        r"\{%\s*\n\s*\\AddToShipoutPictureBG.*?\\null\\clearpage\s*\n\}",
        r"\\begin{center}\n\\includegraphics[width=\\textwidth]{img-000.jpg}\n\\end{center}\n\\clearpage",
        flat,
        flags=re.DOTALL,
    )
    flat = re.sub(r"\\AddToShipoutPictureBG\*\{[^}]*\}\n?", "", flat)
    flat = flat.replace("{images/img-000.jpg}", "{img-000.jpg}")
    flat = flat.replace("{images/img-001.jpg}", "{img-001.jpg}")
    for pkg in (r"\\usepackage\{eso-pic\}", r"\\usepackage\{subfiles\}"):
        flat = re.sub(pkg, "", flat)
    basename = cfg["basename"]
    assert isinstance(basename, str)
    flat_path = out_dir / f"{basename}_flat.tex"
    write_text(flat_path, flat)
    return flat_path


def build_pdf(src_dir: Path, out_dir: Path) -> None:
    basename = next(
        cfg["basename"] for cfg in CONFIGS.values()
        if cfg["src"] == src_dir
    )
    assert isinstance(basename, str)
    pdf_dir = out_dir / "pdf"
    pdf_dir.mkdir(parents=True, exist_ok=True)
    for _ in range(2):
        run([
            "pdflatex",
            "-interaction=nonstopmode",
            f"-jobname={basename}",
            f"-output-directory={pdf_dir}",
            "main.tex",
        ], cwd=src_dir)
    built = pdf_dir / f"{basename}.pdf"
    shutil.copy2(built, out_dir / f"{basename}.pdf")


def build_print_pdf(src_dir: Path, out_dir: Path) -> None:
    basename = next(
        cfg["basename"] for cfg in CONFIGS.values()
        if cfg["src"] == src_dir
    )
    assert isinstance(basename, str)
    main = read_text(src_dir / "main.tex")
    preamble = read_text(src_dir / "preamble.tex")
    patched_preamble = re.sub(
        r"\\geometry\{[^}]*\}",
        lambda _: PRINT_PREAMBLE_PATCH,
        preamble,
    )
    print_main = main.replace(r"\input{preamble}", patched_preamble)
    print_main = print_main.replace(
        r"\documentclass[12pt,a4paper,openany]{book}",
        r"\documentclass[10pt,a5paper,twoside,openright]{book}",
    )
    temp_name = "main_print.generated.tex"
    temp_path = src_dir / temp_name
    write_text(temp_path, print_main)
    print_dir = out_dir / "print"
    print_dir.mkdir(parents=True, exist_ok=True)
    try:
        for _ in range(2):
            run([
                "pdflatex",
                "-interaction=nonstopmode",
                f"-jobname={basename}_print",
                f"-output-directory={print_dir}",
                temp_name,
            ], cwd=src_dir)
    finally:
        if temp_path.exists():
            temp_path.unlink()
    aux_dir = print_dir
    for suffix in ("aux", "log", "out", "toc"):
        extra = aux_dir / f"{basename}_print.{suffix}"
        if extra.exists():
            extra.unlink()


def build_booklet_pdf(src_dir: Path, out_dir: Path) -> None:
    basename = next(
        cfg["basename"] for cfg in CONFIGS.values()
        if cfg["src"] == src_dir
    )
    assert isinstance(basename, str)
    print_dir = out_dir / "print"
    src_pdf = print_dir / f"{basename}_print.pdf"
    dst_pdf = print_dir / f"{basename}_booklet_a4.pdf"
    tex = rf"""\documentclass[a4paper,landscape]{{article}}
\usepackage[margin=0cm]{{geometry}}
\usepackage{{pdfpages}}
\pagestyle{{empty}}
\begin{{document}}
\includepdf[pages=-,signature=4]{{{src_pdf}}}
\end{{document}}
"""
    with tempfile.TemporaryDirectory() as tmp:
        tex_path = Path(tmp) / "booklet.tex"
        write_text(tex_path, tex)
        run([
            "pdflatex",
            "-interaction=nonstopmode",
            f"-output-directory={tmp}",
            str(tex_path),
        ], cwd=ROOT)
        shutil.copy2(Path(tmp) / "booklet.pdf", dst_pdf)


def build_pandoc(cfg: dict[str, object], out_dir: Path, flat_tex: Path) -> None:
    src_dir = cfg["src"]
    title = cfg["title"]
    author = cfg["author"]
    basename = cfg["basename"]
    assert isinstance(src_dir, Path)
    assert isinstance(title, str)
    assert isinstance(author, str)
    assert isinstance(basename, str)
    images_dir = src_dir / "images"
    common = [
        "--resource-path",
        str(images_dir),
        "--metadata",
        f"title={title}",
        "--metadata",
        f"author={author}",
    ]
    markdown_source = re.sub(r"^\s*\\label\{sec:[^}]+\}\s*$\n?", "", read_text(flat_tex), flags=re.MULTILINE)
    with tempfile.NamedTemporaryFile("w", suffix=".tex", delete=False, encoding="utf-8") as tmp:
        tmp.write(markdown_source)
        markdown_flat_tex = Path(tmp.name)
    jobs = {
        f"{basename}.html": ["--standalone", "--self-contained"],
        f"{basename}.epub": [f"--epub-cover-image={images_dir / 'img-000.jpg'}"],
        f"{basename}.fb2": [],
        f"{basename}.md": ["-t", "gfm+footnotes", "--wrap=none", "--standalone", "--toc", "--toc-depth=1"],
    }
    copy_markdown_assets(images_dir, out_dir)
    try:
        for filename, extra in jobs.items():
            source = markdown_flat_tex if filename.endswith('.md') else flat_tex
            run(["pandoc", str(source), "-o", str(out_dir / filename), *extra, *common], cwd=ROOT)
    finally:
        if markdown_flat_tex.exists():
            markdown_flat_tex.unlink()


def clean_aux_files(out_dir: Path) -> None:
    pdf_dir = out_dir / "pdf"
    for rel in [
        *[str(p.relative_to(out_dir)) for p in pdf_dir.glob("*.aux")],
        *[str(p.relative_to(out_dir)) for p in pdf_dir.glob("*.log")],
        *[str(p.relative_to(out_dir)) for p in pdf_dir.glob("*.out")],
        *[str(p.relative_to(out_dir)) for p in pdf_dir.glob("*.toc")],
    ]:
        path = out_dir / rel
        if path.exists():
            path.unlink()


def build_one(name: str) -> None:
    if name not in CONFIGS:
        raise SystemExit(f"Unknown edition: {name}")
    cfg = CONFIGS[name]
    src_dir = cfg["src"]
    assert isinstance(src_dir, Path)
    out_dir = OUT_ROOT / name
    if out_dir.exists():
        shutil.rmtree(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    flat_tex = make_flat_tex(cfg, out_dir)
    build_pdf(src_dir, out_dir)
    build_print_pdf(src_dir, out_dir)
    build_booklet_pdf(src_dir, out_dir)
    build_pandoc(cfg, out_dir, flat_tex)
    clean_aux_files(out_dir)
    print(f"Built {name} -> {out_dir}")


def main(argv: list[str]) -> None:
    targets = argv[1:] if len(argv) > 1 else list(CONFIGS)
    for target in targets:
        build_one(target)


if __name__ == "__main__":
    main(sys.argv)
