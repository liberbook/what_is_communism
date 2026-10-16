#!/usr/bin/env python3
"""Glossary check (no AI): are the glossary targets used in the translation?

For every glossary term that occurs in a source paragraph (any of its '|'
forms, as whole words), the matching paragraph of the translation must
contain the target. Matching tolerates inflection: every word of the target
must appear as a word starting with its stem (the word minus up to three
final letters, at least four letters kept), in any order, within a short window.

Reports the coverage per category and the terms most often missed. Exit
code 1 when the coverage of the 'concept', 'person', 'place', 'acronym' and
'organization' categories is below --min (default 0.9): those must be
rendered consistently. Quotations, titles and phrases are reported only,
because a translator may legitimately rephrase around them.

Usage:
  python3 tools/checks/glossary.py               # every edition with a glossary
  python3 tools/checks/glossary.py en --dir work/en/<run>/reviewed
"""
from __future__ import annotations

import argparse
import collections
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import edlib  # noqa: E402
from structure import translation_blocks  # noqa: E402

STRICT = {"concept", "person", "place", "acronym", "organization", "event"}
WORD = re.compile(r"[^\W\d_]+", re.UNICODE)


def stem(w: str) -> str:
    w = w.lower()
    return w if len(w) <= 4 else w[: max(4, len(w) - 3)]


def words(text: str) -> list[str]:
    return [w.lower() for w in WORD.findall(text.replace("\\", " "))]


def source_regex(forms: list[str]) -> re.Pattern:
    alts = sorted((re.escape(f) for f in forms if f), key=len, reverse=True)
    return re.compile(r"(?<![\w-])(?:" + "|".join(alts) + r")(?![\w-])")


def target_found(target: str, tgt_words: list[str]) -> bool:
    """All stems of the target occur, in any order, within a window of len+3 words."""
    tw = [stem(w) for w in words(target)]
    tw = [w for w in tw if len(w) > 2] or tw   # skip short function words when possible
    if not tw:
        return True
    span = len(tw) + 3
    for i, w in enumerate(tgt_words):
        if not any(w.startswith(s) for s in tw):
            continue
        window = tgt_words[i: i + span]
        if all(any(x.startswith(s) for x in window) for s in tw):
            return True
    return False


def check(ed: edlib.Edition, cfg: edlib.Config, text_dir: Path | None, minimum: float, top: int,
          parts: list[str] | None = None) -> bool:
    gl = json.loads(ed.glossary_path.read_text(encoding="utf-8"))
    terms = [(t, source_regex(t["source"].split("|"))) for t in gl["terms"]]
    src_all = edlib.edition_blocks(cfg.source)
    tgt_all = translation_blocks(ed, text_dir, cfg)
    hits = collections.Counter()
    seen = collections.Counter()
    per_term = collections.defaultdict(lambda: [0, 0])
    misses = collections.defaultdict(list)
    for part_i, (src, tgt) in enumerate(zip(src_all, tgt_all), start=1):
        if parts and f"{part_i:02d}" not in parts:
            continue
        if len(src) != len(tgt):
            print(f"[glossary] {ed.code}: part {part_i:02d} not aligned (paragraph counts differ), skipped")
            continue
        for par_i, (s, t) in enumerate(zip(src, tgt), start=1):
            tw = words(t)
            for term, rx in terms:
                if not rx.search(s):
                    continue
                cat = term["category"]
                seen[cat] += 1
                per_term[term["target"]][1] += 1
                if target_found(term["target"], tw):
                    hits[cat] += 1
                    per_term[term["target"]][0] += 1
                else:
                    misses[term["target"]].append(f"{part_i:02d}§{par_i}")
    strict_seen = sum(v for k, v in seen.items() if k in STRICT)
    strict_hits = sum(v for k, v in hits.items() if k in STRICT)
    coverage = strict_hits / strict_seen if strict_seen else 1.0
    ok = coverage >= minimum
    print(f"[glossary] {ed.code}: {'OK' if ok else 'BELOW THRESHOLD'} strict coverage {coverage:.1%} "
          f"({strict_hits}/{strict_seen}, minimum {minimum:.0%})")
    for cat in sorted(seen):
        print(f"  {cat:<13} {hits[cat]:>4}/{seen[cat]:<4} {hits[cat] / seen[cat]:.0%}")
    worst = sorted(misses.items(), key=lambda kv: (-len(kv[1]), kv[0]))[:top]
    if worst:
        print(f"  most often missing (target: paragraphs):")
        for target, where in worst:
            h, n = per_term[target]
            print(f"    {target!r} {h}/{n}: {' '.join(where[:8])}{' …' if len(where) > 8 else ''}")
    return ok


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("codes", nargs="*")
    ap.add_argument("--dir", type=Path, help="directory of text parts instead of the LaTeX parts")
    ap.add_argument("--min", type=float, default=0.9, help="minimum coverage of the strict categories")
    ap.add_argument("--top", type=int, default=12, help="how many missed terms to list")
    ap.add_argument("--parts", nargs="*", help="only these part numbers, e.g. 03 11")
    args = ap.parse_args()
    cfg = edlib.load_config()
    eds = [cfg.edition(c) for c in args.codes] if args.codes else [e for e in cfg.editions if e.glossary_path]
    ok = True
    for ed in eds:
        if not ed.glossary_path or not ed.glossary_path.exists():
            print(f"[glossary] {ed.code}: no glossary, skipped")
            continue
        ok &= check(ed, cfg, args.dir, args.min, args.top, args.parts)
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
