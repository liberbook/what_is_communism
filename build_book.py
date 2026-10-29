#!/usr/bin/env python3
from __future__ import annotations

import html
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parent
OUT_ROOT = ROOT / "out"
MARKDOWN_IMAGE_SUFFIXES = {".jpg", ".jpeg", ".png", ".gif", ".webp", ".svg"}

LANGUAGES = tomllib.loads((ROOT / "languages.toml").read_text(encoding="utf-8"))
TEMPLATES = ROOT / "tools" / "templates"


def load_configs() -> dict[str, dict[str, object]]:
    """Editions to build, from languages.toml (keyed by source directory name)."""
    return {
        e["dir"]: {
            "src": ROOT / e["dir"],
            "title": e["title"],
            "author": e["author"],
            "lang": e["lang"],
            "basename": e["basename"],
            "edition": e,
        }
        for e in LANGUAGES["edition"]
    }


CONFIGS = load_configs()

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


ICONS = {
    "toc": '<path d="M4 6h16M4 12h16M4 18h10"/>',
    "globe": '<circle cx="12" cy="12" r="9"/><path d="M3 12h18M12 3c2.5 2.7 3.8 5.7 3.8 9s-1.3 6.3-3.8 9c-2.5-2.7-3.8-5.7-3.8-9S9.5 5.7 12 3z"/>',
    "type": '<path d="M4 18 9 6l5 12M5.8 14h6.4M15 18l3-7.5 3 7.5M15.9 16h4.2"/>',
    "download": '<path d="M12 4v11M7 10l5 5 5-5M5 20h14"/>',
}


def icon(name: str) -> str:
    return f'<svg viewBox="0 0 24 24" aria-hidden="true">{ICONS[name]}</svg>'


def html_chrome(cfg: dict[str, object], tmp: Path) -> list[str]:
    """Pandoc arguments for the online edition: template, styles, top bar, script."""
    ed = cfg["edition"]
    assert isinstance(ed, dict)
    e = lambda s: html.escape(str(s), quote=True)
    site = LANGUAGES["site"]
    repo = LANGUAGES["repo"]
    ui = ed["ui"]
    url = f"{site}{ed['code']}/"
    dl = lambda name: f"https://github.com/{repo}/releases/latest/download/{name}"
    b = ed["basename"]
    description = ed.get("about") or ed["title"]
    head = f"""<meta name="description" content="{e(description)}">
<link rel="canonical" href="{url}" data-external="1">
<meta property="og:type" content="book">
<meta property="og:title" content="{e(ed['title'])}">
<meta property="og:description" content="{e(description)}">
<meta property="og:url" content="{url}">
<meta property="og:image" content="{site}og.jpg">
<meta name="twitter:card" content="summary_large_image">
<meta name="theme-color" content="#fbf9f4" media="(prefers-color-scheme: light)">
<meta name="theme-color" content="#1b1a18" media="(prefers-color-scheme: dark)">
<link rel="icon" href="{site}favicon.svg" type="image/svg+xml" data-external="1">
<link rel="preconnect" href="https://fonts.googleapis.com" data-external="1">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin data-external="1">
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Literata:ital,opsz,wght@0,7..72,400;0,7..72,600;0,7..72,700;1,7..72,400&amp;display=swap" data-external="1">
<script>try{{var t=localStorage.getItem("wic:theme");if(t==="light"||t==="dark")document.documentElement.dataset.theme=t;var f=localStorage.getItem("wic:fs");if(f)document.documentElement.style.setProperty("--fs",f+"px")}}catch(e){{}}</script>
<style>
{read_text(TEMPLATES / "edition.css")}</style>"""
    langs = []
    for other in LANGUAGES["edition"]:
        current = ' aria-current="true"' if other["code"] == ed["code"] else ""
        langs.append(f'<a href="{site}{other["code"]}/" data-base="{site}{other["code"]}/" data-parts="{e(" ".join(other["parts"]))}" '
                     f'lang="{other["lang"]}" hreflang="{other["lang"]}"{current}>'
                     f'{e(other["name"])}<small>{other["code"].upper()}</small></a>')
    files = ed["files"]
    downloads = "".join(f'<a href="{dl(name)}">{e(label)}<small>{ext}</small></a>' for label, name, ext in [
        (files["pdf"], f"{b}.pdf", "A4"), (files["print"], f"{b}_print.pdf", "A5"), (files["booklet"], f"{b}_booklet_a4.pdf", "A4"),
        ("EPUB", f"{b}.epub", "epub"), ("FB2", f"{b}.fb2", "fb2")])
    data = json.dumps({"key": ed["code"], "ui": ui}, ensure_ascii=False).replace("</", "<\\/")
    before = f"""<header class="topbar">
<button class="btn only-narrow" id="toc-btn" type="button" aria-label="{e(ed.get('contents', 'Contents'))}">{icon("toc")}</button>
<a class="book" href="{site}"><b>{e(ed['title'])}</b> · {e(ed['author'])}</a>
<details class="menu"><summary class="btn" aria-label="{e(ui['languages'])}">{icon("globe")}<span class="only-wide">{ed['code'].upper()}</span></summary>
<div class="pop">{"".join(langs)}<hr><a href="{site}">{e(ui['languages'])} →</a></div></details>
<details class="menu"><summary class="btn" aria-label="{e(ed['download'])}">{icon("download")}</summary>
<div class="pop"><span class="label">{e(ed['download'])}</span>{downloads}</div></details>
<details class="menu"><summary class="btn" aria-label="{e(ui['theme'])}, {e(ui['text_size'])}">{icon("type")}</summary>
<div class="pop"><span class="label">{e(ui['text_size'])}</span>
<div class="seg"><button type="button" data-fs="-1" aria-label="−">A−</button><button type="button" data-fs="1" aria-label="+">A+</button></div>
<span class="label">{e(ui['theme'])}</span>
<div class="seg"><button type="button" data-theme-set="auto">{e(ui['auto'])}</button><button type="button" data-theme-set="light">{e(ui['light'])}</button><button type="button" data-theme-set="dark">{e(ui['dark'])}</button></div></div></details>
<div class="progress" aria-hidden="true"></div>
</header>
<div class="scrim" aria-hidden="true"></div>"""
    after = f"""<script id="edition-data" type="application/json">{data}</script>
<script>
{read_text(TEMPLATES / "edition.js")}</script>"""
    paths = {}
    for name, content in {"head": head, "before": before, "after": after}.items():
        paths[name] = tmp / f"{name}.html"
        write_text(paths[name], content)
    return ["--template", str(TEMPLATES / "edition.html"), "--section-divs",
            "-V", f"toc-title={ed.get('contents', 'Contents')}",
            "-H", str(paths["head"]), "-B", str(paths["before"]), "-A", str(paths["after"])]


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
        "--metadata",
        f"lang={cfg['lang']}",
    ]
    markdown_source = re.sub(r"^\s*\\label\{sec:[^}]+\}\s*$\n?", "", read_text(flat_tex), flags=re.MULTILINE)
    with tempfile.NamedTemporaryFile("w", suffix=".tex", delete=False, encoding="utf-8") as tmp:
        tmp.write(markdown_source)
        markdown_flat_tex = Path(tmp.name)
    chrome_dir = Path(tempfile.mkdtemp())
    jobs = {
        f"{basename}.html": ["--standalone", "--self-contained", "--toc", "--toc-depth=1", *html_chrome(cfg, chrome_dir)],
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
        shutil.rmtree(chrome_dir, ignore_errors=True)


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
