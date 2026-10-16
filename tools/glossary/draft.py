#!/usr/bin/env python3
"""Draft the glossary targets of one language with the model (Claude Code CLI).

Every source in glossary/terms.json that has no target yet in
glossary/targets.<code>.json is sent to the model in batches, together with
its category and the English and Italian targets as reference. The result is
written with "status": "draft"; targets the model is unsure about carry a
"note". Review the file by hand (fix targets, delete notes), then set
"status": "reviewed" so tools/glossary/build.py accepts it.

Existing targets are never overwritten, so the same command fills in only
the new sources after terms.json grows.

Usage: python3 tools/glossary/draft.py de [--model opus] [--delay 10] [--batch 60]
"""
from __future__ import annotations

import argparse
import asyncio
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import edlib  # noqa: E402

edlib.use_tbl()
from src.core.llm.providers.claude_cli import ClaudeCliProvider, ClaudeUsageLimitError  # noqa: E402

GLOSSARY_DIR = edlib.ROOT / "glossary"

SYSTEM = """You are a terminologist preparing the Russian -> {lang} glossary for the translation of a Marxist theoretical booklet («Что такое коммунизм?», Engels Group, 2018). The glossary is injected into every chunk of the translation, so each target must be the single best, canonical {lang} rendering.

Rules:
- Proper names: the spelling used by {lang} Wikipedia (established forms for Marx, Engels, Lenin, Hegel...).
- Titles of works: the established {lang} title of the work; translate carefully only if none exists.
- Quotations and formulas of Marx, Engels and Lenin: the wording of the standard {lang} editions, when you are confident of it.
- Concepts: the established {lang} Marxist and philosophical lexicon. Keep distinct Russian terms distinct (e.g. снятие / упразднение / уничтожение; частная / личная / общая / общественная собственность; освоение / присвоение).
- The target is the dictionary form; it will be inflected in the text as {lang} grammar requires.
- The English and Italian targets are reference renderings of the same term; follow their sense, not their wording.

Answer ONLY with a JSON object mapping every given source to {{"target": "...", "note": "..."}}. Give a note (one short line, in English) only when you are not sure, e.g. a quotation whose standard wording you cannot recall exactly; otherwise use an empty note."""


def batches(items: list, n: int):
    for i in range(0, len(items), n):
        yield items[i:i + n]


def parse(text: str) -> dict:
    m = re.search(r"\{.*\}", text, re.S)
    return json.loads(m.group(0)) if m else {}


async def run(args: argparse.Namespace) -> int:
    cfg = edlib.load_config()
    ed = cfg.edition(args.code)
    if not ed.translated:
        raise SystemExit(f"edition {ed.code} has no target_language in languages.toml")
    terms = json.loads((GLOSSARY_DIR / "terms.json").read_text(encoding="utf-8"))["terms"]
    refs = {}
    for code in ("en", "it"):
        p = GLOSSARY_DIR / f"targets.{code}.json"
        if p.exists() and code != ed.code:
            refs[code] = json.loads(p.read_text(encoding="utf-8"))["targets"]
    out_path = GLOSSARY_DIR / f"targets.{ed.code}.json"
    doc = json.loads(out_path.read_text(encoding="utf-8")) if out_path.exists() else {
        "language": ed.target_language, "status": "draft",
        "name": f"What is communism (ru -> {ed.code})",
        "about": (f"Glossary for the whole booklet, built by tools/glossary/build.py {ed.code} from glossary/terms.json "
                  f"and glossary/targets.{ed.code}.json. Each source lists the inflected forms found in the Russian "
                  "text, separated by '|', so TranslateBooksWithLLMs' per-chunk filter matches them."),
        "targets": {},
    }
    todo = [t for t in terms if t["source"] not in doc["targets"]]
    print(f"{len(todo)} of {len(terms)} sources need a {ed.target_language} target")
    if not todo:
        return 0
    provider = ClaudeCliProvider(model=args.model, delay_seconds=args.delay)
    try:
        for i, batch in enumerate(batches(todo, args.batch), start=1):
            items = [{"source": t["source"], "category": t["category"],
                      **{f"{c}_reference": (r[t["source"]]["target"] if isinstance(r[t["source"]], dict) else r[t["source"]])
                         for c, r in refs.items() if t["source"] in r}} for t in batch]
            prompt = "Sources:\n" + json.dumps(items, ensure_ascii=False, indent=1)
            got: dict = {}
            for attempt in range(3):
                resp = await provider.generate(prompt, timeout=900, system_prompt=SYSTEM.format(lang=ed.target_language))
                try:
                    got = parse(resp.content if resp else "")
                except json.JSONDecodeError:
                    got = {}
                missing = [t["source"] for t in batch if t["source"] not in got]
                if not missing:
                    break
                print(f"batch {i}: {len(missing)} sources missing from the answer, retrying")
            added = 0
            for t in batch:
                v = got.get(t["source"])
                if not v:
                    continue
                target = (v.get("target") if isinstance(v, dict) else str(v)).strip()
                note = (v.get("note") or "").strip() if isinstance(v, dict) else ""
                if target:
                    doc["targets"][t["source"]] = {"target": target, "note": f"CHECK: {note}"} if note else target
                    added += 1
            doc["status"] = "draft"
            out_path.write_text(json.dumps(doc, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
            print(f"batch {i}: {added}/{len(batch)} targets written to {edlib.rel(out_path)}")
    except ClaudeUsageLimitError as e:
        print(f"usage limit reached ({e}); progress is saved, rerun later to continue")
        return 75
    finally:
        await provider.close()
    left = [t["source"] for t in terms if t["source"] not in doc["targets"]]
    notes = sum(1 for v in doc["targets"].values() if isinstance(v, dict) and v.get("note", "").startswith("CHECK"))
    print(f"done: {len(terms) - len(left)}/{len(terms)} targets, {notes} marked CHECK; still missing: {left[:10]}")
    print(f'review {edlib.rel(out_path)}, then set "status": "reviewed" and run: python3 tools/glossary/build.py {ed.code}')
    return 0 if not left else 1


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("code")
    ap.add_argument("--model", default="opus")
    ap.add_argument("--delay", type=float, default=10.0, help="seconds between model calls")
    ap.add_argument("--batch", type=int, default=60)
    args = ap.parse_args()
    sys.exit(asyncio.run(run(args)))


if __name__ == "__main__":
    main()
