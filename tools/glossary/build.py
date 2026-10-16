#!/usr/bin/env python3
"""Build the translation glossary of one or more editions.

Inputs (in glossary/):
  terms.json            Russian sources shared by every language: category and,
                        when automatic matching is not reliable, hand-listed forms
  targets.<code>.json   the target of every source in one language, with
                        "status": "draft" (made by draft.py) or "reviewed"

Output: the file named by `glossary` in languages.toml for that edition, in the
format TranslateBooksWithLLMs' --glossary expects. Every source lists the
inflected forms found in the Russian text (russian/parts/*.tex), separated by
'|', because the translator's per-chunk filter matches source terms literally.

Exit code 1 when a target file is incomplete, has unknown sources, or is still
a draft (use --allow-draft to build from a draft anyway).

Usage:
  python3 tools/glossary/build.py it en        # selected editions
  python3 tools/glossary/build.py --all        # every edition that has a glossary
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from edlib import ROOT, edition_blocks, load_config, rel  # noqa: E402

GLOSSARY_DIR = ROOT / "glossary"
CYR_TOKEN = re.compile(r"[А-Яа-яЁё]+(?:-[А-Яа-яЁё]+)*")


# Inflectional endings that may follow a stem (nouns, adjectives, participles).
ENDINGS = sorted({
    "ями", "ами", "иями", "ого", "его", "ому", "ему", "ыми", "ими", "ых", "их", "ым", "им",
    "ый", "ием", "ией", "иям", "иях", "ой", "ей", "ою", "ею", "ом", "ем", "ём", "ах", "ях", "ам", "ям", "ов", "ев", "ёв",
    "ия", "ие", "ий", "ии", "ию", "ую", "юю", "ая", "яя", "ое", "ее", "ые", "ью",
    "а", "я", "ы", "и", "у", "ю", "е", "ё", "о", "ь", "й",
}, key=len, reverse=True)
MIN_STEM = 3
CYR_TOKEN = re.compile(r"[А-Яа-яЁё]+(?:-[А-Яа-яЁё]+)*")


def stem(word: str) -> str:
    """Strip the longest inflectional ending (final hyphen segment only)."""
    w = word.lower()
    head, sep, tail = w.rpartition("-")
    for e in ENDINGS:
        if tail.endswith(e) and len(tail) - len(e) >= MIN_STEM:
            tail = tail[: -len(e)]
            break
    return f"{head}{sep}{tail}" if sep else tail


def matches(token: str, term_word: str) -> bool:
    """True when `token` is an inflected form of `term_word`.

    Two candidate stems are tried: the word itself (surnames in -ов/-ин, words
    whose apparent ending is part of the stem) and the word minus its longest
    inflectional ending. ё and е are treated alike because the source text
    spells many words without ё.
    """
    t = token.lower().replace("ё", "е")
    w = term_word.lower().replace("ё", "е")
    for s in (w, stem(w)):
        if t.startswith(s):
            rest = t[len(s):]
            if rest == "" or rest in ENDINGS:
                return True
    return False


SENTENCE_PUNCT = re.compile(r"[.;!?]")


def corpus_variants(source: str, corpus: str, tokens: list[tuple[str, int, int]]) -> list[str]:
    """Surface forms of `source` found in the corpus (inflected variants)."""
    words = CYR_TOKEN.findall(source)
    if not words or re.search(r"[A-Za-z0-9]", source):
        return []
    n = len(words)
    upper_only = source[0].isupper()
    found: dict[str, None] = {}
    for i in range(len(tokens) - n + 1):
        if not all(matches(tokens[i + k][0], words[k]) for k in range(n)):
            continue
        surface = re.sub(r"\s+", " ", corpus[tokens[i][1]: tokens[i + n - 1][2]])
        if upper_only and not surface[0].isupper():
            continue
        if n > 1 and (len(surface) > len(source) * 1.5 + 6 or
                      len(SENTENCE_PUNCT.findall(surface)) > len(SENTENCE_PUNCT.findall(source))):
            continue
        found[surface] = None
    return list(found)


def russian_corpus() -> str:
    """Plain text of the Russian parts, in the simple export format."""
    cfg = load_config()
    return "\n\n".join("\n\n".join(blocks) for blocks in edition_blocks(cfg.source))


def load_terms() -> list[dict]:
    return json.loads((GLOSSARY_DIR / "terms.json").read_text(encoding="utf-8"))["terms"]


def load_targets(code: str) -> dict:
    path = GLOSSARY_DIR / f"targets.{code}.json"
    if not path.exists():
        raise SystemExit(f"{rel(path)} does not exist: run python3 tools/glossary/draft.py {code}")
    return json.loads(path.read_text(encoding="utf-8"))


def validate(code: str, terms: list[dict], doc: dict, allow_draft: bool) -> list[str]:
    errors = []
    targets = doc.get("targets", {})
    sources = [t["source"] for t in terms]
    missing = [s for s in sources if s not in targets]
    empty = [s for s in sources if s in targets and not (targets[s]["target"] if isinstance(targets[s], dict) else targets[s]).strip()]
    unknown = [s for s in targets if s not in sources]
    if missing:
        errors.append(f"{len(missing)} sources without a target, e.g. {missing[:5]}")
    if empty:
        errors.append(f"{len(empty)} empty targets, e.g. {empty[:5]}")
    if unknown:
        errors.append(f"{len(unknown)} targets for sources not in terms.json, e.g. {unknown[:5]}")
    if doc.get("status") != "reviewed" and not allow_draft:
        errors.append(f'status is "{doc.get("status")}": review the targets, then set "status": "reviewed"')
    return [f"targets.{code}.json: {e}" for e in errors]


def build(code: str, out: Path, terms: list[dict], doc: dict, corpus: str, tokens: list) -> list[str]:
    unmatched = []
    entries = []
    for t in terms:
        source = t["source"]
        variants = [v for v in t["forms"] if v != source] if "forms" in t else corpus_variants(source, corpus, tokens)
        if not variants and source not in corpus:
            unmatched.append(source)
        value = doc["targets"][source]
        target, note = (value["target"], value.get("note", "")) if isinstance(value, dict) else (value, "")
        entry = {"source": "|".join([source] + [v for v in variants if v != source]), "target": target,
                 "category": t["category"]}
        if note:
            entry["_note"] = note
        entries.append(entry)
    glossary = {"name": doc["name"], "_about": doc["about"], "terms": entries}
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(glossary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    forms = sum(len(e["source"].split("|")) for e in entries)
    print(f"wrote {rel(out)}: {len(entries)} terms, {forms} source forms")
    return unmatched


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("codes", nargs="*", help="edition codes (e.g. it en)")
    ap.add_argument("--all", action="store_true", help="every edition that has a glossary in languages.toml")
    ap.add_argument("--allow-draft", action="store_true", help="build even if the targets are still a draft")
    ap.add_argument("--out", type=Path, help="output file (only with a single code)")
    args = ap.parse_args()
    cfg = load_config()
    eds = [e for e in cfg.editions if e.glossary_path] if args.all else [cfg.edition(c) for c in args.codes]
    if not eds:
        ap.error("give edition codes or --all")
    terms = load_terms()
    corpus = russian_corpus()
    tokens = [(m.group(0), m.start(), m.end()) for m in CYR_TOKEN.finditer(corpus)]
    failed = False
    for ed in eds:
        if not ed.glossary_path:
            raise SystemExit(f"edition {ed.code} has no glossary in languages.toml")
        doc = load_targets(ed.code)
        errors = validate(ed.code, terms, doc, args.allow_draft)
        if errors:
            failed = True
            for e in errors:
                print("ERROR", e)
            continue
        unmatched = build(ed.code, args.out or ed.glossary_path, terms, doc, corpus, tokens)
        if unmatched:
            print(f"  {len(unmatched)} sources never occur in the Russian text: {unmatched}")
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()
