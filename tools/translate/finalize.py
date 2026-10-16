#!/usr/bin/env python3
"""Turn a run's reviewed text into the LaTeX parts of the edition.

For every part of work/<code>/<run>/reviewed/ (or draft/ with --from draft):
  1. typography from [typography] in languages.toml: quotation marks by nesting
     level (« » “ ” „ and straight quotes in the input), parenthetical dashes,
     number ranges, ellipsis, spacing;
  2. LaTeX escaping of % & # $ _ ~ ^ that are not escaped yet;
  3. import into <dir>/parts/<part>.tex with parts_text_exchange.py (footnotes
     re-attached from their [n] markers, page numbers and labels kept).
Warnings (unbalanced quotes, leftover Cyrillic) are printed; the structural
check in tools/checks/structure.py verifies the result.

Usage: python3 tools/translate/finalize.py en [--run NAME | --dir PATH] [--from reviewed|draft] [--dry-run]
"""
from __future__ import annotations

import argparse
import re
import subprocess
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import edlib  # noqa: E402

UNESCAPED = re.compile(r"(?<!\\)([%&#$_])")


def quotes(par: str, typo: dict, warn) -> str:
    (o1, c1), (o2, c2) = typo["quotes"], typo["inner_quotes"]
    par = par.replace("<<", "«").replace(">>", "»")
    straight_ok = par.count('"') % 2 == 0
    if not straight_ok:
        warn("odd number of straight double quotes, left as is")
    closes_with_ldquo = "“" in (c1, c2)          # German-style „…“: “ closes
    out, depth, straight_open = [], 0, False

    def open_q():
        nonlocal depth
        out.append(o1 if depth == 0 else o2)
        depth += 1

    def close_q():
        nonlocal depth
        depth = max(depth - 1, 0)
        out.append(c1 if depth == 0 else c2)

    for ch in par:
        if ch in "«„":
            open_q()
        elif ch in "»”":
            close_q()
        elif ch == "“":
            close_q() if (closes_with_ldquo and depth > 0) else open_q()
        elif ch == '"' and straight_ok:
            close_q() if straight_open else open_q()
            straight_open = not straight_open
        else:
            out.append(ch)
    if depth:
        warn("unbalanced quotation marks (normal when a quotation continues in the next paragraph)")
    return "".join(out)


def typography(par: str, typo: dict, warn) -> str:
    par = quotes(par, typo, warn)
    par = re.sub(r"(\d)\s*[—–-]\s*(\d)", lambda m: m.group(1) + typo["range_dash"] + m.group(2), par)
    dash = typo["dash"]
    if typo["spaced_dash"]:
        par = re.sub(r"\s+[–—-]\s+", f" {dash} ", par)
        par = re.sub(r"(?<=\S)—(?=\S)", f" {dash} ", par)
    else:
        par = re.sub(r"\s+[–—]\s+|\s+-\s+", dash, par)
    par = par.replace("...", "…")
    (o1, c1) = typo["quotes"]
    if o1 in "«“„":
        par = par.replace(o1 + " ", o1)
    if c1 in "»”“":
        par = par.replace(" " + c1, c1)
    return re.sub(r"[ \t]{2,}", " ", par).strip()


def latex_escape(par: str) -> str:
    par = UNESCAPED.sub(r"\\\1", par)
    par = re.sub(r"(?<!\\)~", r"\\textasciitilde{}", par)
    return re.sub(r"(?<!\\)\^", r"\\textasciicircum{}", par)


def prepare(blocks: list[str], typo: dict, name: str, warnings: list[str]) -> str:
    out = []
    for i, b in enumerate(blocks, start=1):
        b = latex_escape(typography(b, typo, lambda m, i=i: warnings.append(f"{name} §{i}: {m}")))
        if re.search(r"[Ѐ-ӿ]", b):
            warnings.append(f"{name} §{i}: Cyrillic letters remain")
        out.append(b)
    return "\n\n".join(out) + "\n"


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("code")
    ap.add_argument("--run", help="run name under work/<code>/")
    ap.add_argument("--dir", type=Path, help="any directory of translated text parts (instead of --run)")
    ap.add_argument("--from", dest="stage", choices=("reviewed", "draft"), default="reviewed")
    ap.add_argument("--dry-run", action="store_true", help="write the prepared text to <run>/final/ only")
    ap.add_argument("--parts", nargs="*", help="only these part numbers, e.g. 03 11")
    args = ap.parse_args()
    cfg = edlib.load_config()
    ed = cfg.edition(args.code)
    if not ed.translated:
        raise SystemExit(f"edition {ed.code} has no [typography]: not a pipeline translation")
    if args.dir:
        src_dir = args.dir
    elif args.run:
        src_dir = edlib.run_dir(ed.code, args.run) / args.stage
    else:
        raise SystemExit("give --run NAME or --dir PATH")
    warnings: list[str] = []
    sources = edlib.source_txt_paths(cfg)
    with tempfile.TemporaryDirectory() as tmp:
        imp = Path(tmp)
        for src, slug in zip(sources, ed.parts):
            if args.parts and src.name[:2] not in args.parts:
                continue
            text_path = src_dir / src.name
            if not text_path.exists():
                raise SystemExit(f"missing {edlib.rel(text_path)}")
            page = src.stem.rsplit("__p", 1)[1]
            (imp / f"{slug}__p{page}.txt").write_text(
                prepare(edlib.read_text_blocks(text_path), ed.typography, src.name, warnings), encoding="utf-8")
        if args.dry_run:
            final = src_dir.parent / "final"
            final.mkdir(exist_ok=True)
            for f in imp.glob("*.txt"):
                (final / f.name).write_text(f.read_text(encoding="utf-8"), encoding="utf-8")
            print(f"prepared text written to {edlib.rel(final)}")
        else:
            ed.parts_dir.mkdir(parents=True, exist_ok=True)
            subprocess.run([sys.executable, str(edlib.ROOT / "parts_text_exchange.py"), "import", str(imp), str(ed.parts_dir)],
                           check=True, stdout=subprocess.DEVNULL)
            gitkeep = ed.parts_dir / ".gitkeep"
            if gitkeep.exists():
                gitkeep.unlink()
            print(f"wrote {len(list(imp.glob('*.txt')))} parts to {edlib.rel(ed.parts_dir)}")
    for w in warnings:
        print("WARNING", w)


if __name__ == "__main__":
    main()
