#!/usr/bin/env python3
"""Structural check of translated editions against the Russian source (no AI).

For every part, the source and the translation (LaTeX parts of the edition,
or a directory of text parts with --dir) are compared:
  errors    paragraph count, footnote markers and footnotes, Cyrillic letters
            left in a non-Cyrillic edition, unescaped LaTeX specials, quotation
            marks foreign to the edition's typography, unbalanced braces
  warnings  numbers of the source missing in the translation, paragraphs whose
            length ratio is suspicious (possible omission or padding)

Exit code 1 when any error is found.

Usage:
  python3 tools/checks/structure.py                 # every translated edition
  python3 tools/checks/structure.py en it
  python3 tools/checks/structure.py en --dir work/en/<run>/reviewed --no-typography
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import edlib  # noqa: E402

CYRILLIC = re.compile(r"[Ѐ-ӿ]")
CYRILLIC_LANGS = {"ru", "uk", "be", "bg", "sr", "mk", "kk", "ky", "tg", "mn"}
UNESCAPED = re.compile(r"(?<!\\)[%&#$_^~]")
NUMBER = re.compile(r"\d+")
FN = re.compile(r"\[(\d+)\]")
QUOTE_CHARS = set("«»“”„‟‹›\"")


def split_notes(blocks: list[str]) -> tuple[list[str], list[str]]:
    body = list(blocks)
    notes: list[str] = []
    while body and re.match(r"^\[\d+\]\s+", body[-1]):
        notes.insert(0, body.pop())
    return body, notes


def check_part(name: str, src: list[str], tgt: list[str], ed: edlib.Edition, typography: bool,
               lo: float, hi: float) -> tuple[list[str], list[str]]:
    errors: list[str] = []
    warnings: list[str] = []
    if not tgt:
        return [f"{name}: translation missing"], []
    if len(src) != len(tgt):
        errors.append(f"{name}: {len(tgt)} paragraphs, source has {len(src)}")
    sb, sn = split_notes(src)
    tb, tn = split_notes(tgt)
    if FN.findall("\n".join(sb)) != FN.findall("\n".join(tb)):
        errors.append(f"{name}: footnote markers {FN.findall(chr(10).join(tb))}, source {FN.findall(chr(10).join(sb))}")
    if len(sn) != len(tn):
        errors.append(f"{name}: {len(tn)} footnotes, source has {len(sn)}")
    text = "\n\n".join(tgt)
    if ed.lang not in CYRILLIC_LANGS and CYRILLIC.search(text):
        sample = sorted(set(re.findall(r"\S*[Ѐ-ӿ]+\S*", text)))[:6]
        errors.append(f"{name}: Cyrillic letters left: {sample}")
    unesc = UNESCAPED.findall(text)
    if unesc:
        errors.append(f"{name}: unescaped LaTeX specials {sorted(set(unesc))}")
    if text.count("{") != text.count("}"):
        errors.append(f"{name}: unbalanced braces ({text.count('{')} vs {text.count('}')})")
    if typography and ed.get("typography"):
        t = ed.typography
        allowed = set(t["quotes"]) | set(t["inner_quotes"])
        foreign = sorted({c for c in text if c in QUOTE_CHARS} - allowed)
        if foreign:
            errors.append(f"{name}: quotation marks foreign to the {ed.code} typography: {foreign}")
        if "<<" in text or ">>" in text:
            errors.append(f"{name}: << or >> left")
    missing = sorted(set(NUMBER.findall("\n".join(src))) - set(NUMBER.findall(text)), key=int)
    if missing:
        warnings.append(f"{name}: numbers of the source not found: {missing} (may be written out)")
    if len(src) == len(tgt):
        for i, (a, b) in enumerate(zip(src, tgt), start=1):
            if len(a) >= 80 and not lo <= len(b) / len(a) <= hi:
                warnings.append(f"{name} §{i}: length ratio {len(b) / len(a):.2f}")
    return errors, warnings


def find_part(text_dir: Path, source_name: str) -> Path | None:
    """The text part for a source part: same file name, or same NN_ prefix."""
    exact = text_dir / source_name
    if exact.exists():
        return exact
    found = sorted(text_dir.glob(f"{source_name[:3]}*.txt"))
    return found[0] if found else None


def translation_blocks(ed: edlib.Edition, text_dir: Path | None, cfg: edlib.Config) -> list[list[str]]:
    if text_dir is None:
        return edlib.edition_blocks(ed)
    out = []
    for p in edlib.source_txt_paths(cfg):
        f = find_part(text_dir, p.name)
        out.append(edlib.read_text_blocks(f) if f else [])
    return out


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("codes", nargs="*", help="editions (default: every edition except the source)")
    ap.add_argument("--dir", type=Path, help="check a directory of text parts instead of the LaTeX parts")
    ap.add_argument("--no-typography", action="store_true", help="skip the quotation-mark check (raw model output)")
    ap.add_argument("--ratio", nargs=2, type=float, default=(0.7, 1.9), metavar=("LOW", "HIGH"))
    ap.add_argument("--parts", nargs="*", help="only these part numbers, e.g. 03 11")
    ap.add_argument("-q", "--quiet", action="store_true", help="print errors only")
    args = ap.parse_args()
    cfg = edlib.load_config()
    eds = [cfg.edition(c) for c in args.codes] if args.codes else [e for e in cfg.editions if not e.is_source]
    src_all = edlib.edition_blocks(cfg.source)
    n_err = 0
    for ed in eds:
        tgt_all = translation_blocks(ed, args.dir, cfg)
        errs, warns = [], []
        for src_path, src, tgt in zip(cfg.source.part_paths(), src_all, tgt_all):
            if args.parts and src_path.stem[:2] not in args.parts:
                continue
            e, w = check_part(src_path.stem[:2], src, tgt, ed, not args.no_typography, *args.ratio)
            errs += e
            warns += w
        print(f"[structure] {ed.code}: {'OK' if not errs else f'{len(errs)} error(s)'}, {len(warns)} warning(s)")
        for e in errs:
            print(f"  ERROR   {e}")
        if not args.quiet:
            for w in warns:
                print(f"  warning {w}")
        n_err += len(errs)
    sys.exit(1 if n_err else 0)


if __name__ == "__main__":
    main()
