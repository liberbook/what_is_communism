#!/usr/bin/env python3
"""Pass 2: bilingual review of the draft against the Russian source.

For every part, consecutive paragraphs are grouped into chunks of at most
--max-src-tokens source tokens. The model receives the Russian paragraphs, the
draft paragraphs and the glossary entries that occur in the chunk, and returns
the revised paragraphs (same [[Pn]] markers, same count). Language rules come
from the edition's [prompt] section in languages.toml.

Reads work/<code>/<run>/draft/, writes work/<code>/<run>/reviewed/ plus a
.changes.diff per part. Progress is saved per chunk, so rerunning resumes; on
the subscription usage limit the script sleeps until the reset and goes on.

Usage: python3 tools/translate/pass2.py en [--run NAME] [--model opus] [--delay 10]
"""
from __future__ import annotations

import argparse
import asyncio
import difflib
import json
import os
import re
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import edlib  # noqa: E402

edlib.use_tbl()
os.environ.setdefault("MAX_THINKING_TOKENS", "3000")  # a small thinking budget helps the comparison
from src.core.chunking.token_chunker import count_tokens  # noqa: E402
from src.core.glossary.cli_loader import load_glossary_from_file  # noqa: E402
from src.core.glossary.filter import filter_glossary  # noqa: E402
from src.core.glossary.injector import build_glossary_block  # noqa: E402
from src.core.glossary.models import GlossaryConfig  # noqa: E402
from src.core.llm.exceptions import RateLimitError  # noqa: E402
from src.core.llm.providers.claude_cli import ClaudeCliProvider, ClaudeUsageLimitError  # noqa: E402

TAG_IN = "<REVISED>"
TAG_OUT = "</REVISED>"
MARKER = re.compile(r"^\[\[P(\d+)\]\]\s*$", re.M)

SYSTEM_PROMPT_TEMPLATE = """You are a senior reviser of Russian-to-{lang} translations: a native {lang} writer with a thorough knowledge of Marxist theory and of how Marx, Engels and Lenin are quoted in {lang}. You receive the Russian source and a draft {lang} translation of a political-theoretical essay, aligned paragraph by paragraph. Produce the final {lang} version.

# WHAT TO CHECK, PARAGRAPH BY PARAGRAPH
1. Meaning: fix mistranslations, misread syntax, wrong referents, inverted logic.
2. Completeness: restore omitted clauses or sentences; remove anything added that is not in the source. Do not summarize.
3. Terminology: the glossary below is mandatory; apply it consistently (adapt it as {lang} grammar requires, never substitute a different rendering). Keep distinct Russian terms distinct in {lang} ({distinct}).
4. Names and quotations: proper names in scientific transliteration as in the glossary; well-known formulas of Marx, Engels and Lenin in their established {lang} wording ({canon}).
5. Numbers, dates, percentages: identical to the source. {numbers}
6. Register: a theoretical essay with a polemical, at times sarcastic, voice; natural literate {lang}, no bureaucratic calques from Russian, no false friends. Keep the author's irony, scare quotes and coinages (e.g. {coinage}).
7. {typography}
8. Grammar, agreement, spelling.

# WHAT TO PRESERVE EXACTLY
- The paragraph markers [[Pn]] and the number of paragraphs: every input paragraph yields exactly one output paragraph with the same marker. Never merge or split paragraphs.
- Footnote markers such as [1] at the position where the source has them; footnote paragraphs stay footnote paragraphs ("[1] text of the note").
- The LaTeX escape \\% (backslash + percent sign) wherever a percentage appears.
- The first paragraph is the section title: keep it a short title line.
- The source's emphasis: words or sentences set in ALL CAPS in the Russian stay in ALL CAPS in {lang}; quotation marks around titles only where the source has them.
- No translator's notes, comments, brackets or explanations of any kind. Nothing outside the tags.
- When a paragraph is already correct, return it unchanged. Prefer the draft's wording whenever it is right: do not rewrite for the sake of rewriting.

# OUTPUT FORMAT
Respond ONLY with:
<REVISED>
[[P1]]
revised paragraph 1

[[P2]]
revised paragraph 2
</REVISED>
Each marker on its own line, paragraphs separated by one blank line. Start with <REVISED> and end with </REVISED>; nothing before or after."""


def system_prompt(ed: edlib.Edition) -> str:
    return SYSTEM_PROMPT_TEMPLATE.format(lang=ed.target_language, **ed.prompt)


RETRY_NOTE = ("\n\nIMPORTANT: your previous answer for this exact chunk did not contain exactly the "
              "expected markers {markers}. Output every marker exactly once, in order, each on its own line.")


def blocks(text: str) -> list[str]:
    return [b.strip() for b in re.split(r"\n\s*\n", text.strip()) if b.strip()]


def numbered(paragraphs: list[str], start: int) -> str:
    return "\n\n".join(f"[[P{start + i}]]\n{p}" for i, p in enumerate(paragraphs))


def parse_response(text: str, expected: list[int]) -> list[str] | None:
    if TAG_IN in text:
        text = text.split(TAG_IN, 1)[1]
    if TAG_OUT in text:
        text = text.split(TAG_OUT, 1)[0]
    positions = list(MARKER.finditer(text))
    found = [int(m.group(1)) for m in positions]
    if found != expected:
        return None
    out: list[str] = []
    for i, m in enumerate(positions):
        end = positions[i + 1].start() if i + 1 < len(positions) else len(text)
        out.append(text[m.end():end].strip())
    if any(not p for p in out):
        return None
    return out


def make_chunks(src: list[str], max_tokens: int) -> list[tuple[int, int]]:
    chunks: list[tuple[int, int]] = []
    start = 0
    tokens = 0
    for i, p in enumerate(src):
        t = count_tokens(p)
        if i > start and tokens + t > max_tokens:
            chunks.append((start, i))
            start, tokens = i, 0
        tokens += t
    chunks.append((start, len(src)))
    return chunks



def blocks_of(path: Path) -> list[str]:
    return edlib.read_text_blocks(path)


class UsageLimit(Exception):
    def __init__(self, resets_at):
        super().__init__(resets_at)
        self.resets_at = resets_at


async def review_part(ed, provider, src_path: Path, draft_path: Path, out_path: Path, glossary, args) -> list[int]:
    lang = ed.target_language
    src = blocks_of(src_path)
    draft = blocks_of(draft_path)
    if len(src) != len(draft):
        raise SystemExit(f"{draft_path.name}: paragraph count differs: source {len(src)}, draft {len(draft)}")
    terms, meta = glossary
    gconfig = GlossaryConfig(max_entries=args.max_glossary_entries)
    chunks = make_chunks(src, args.max_src_tokens)
    progress_path = Path(f"{out_path}.progress.json")
    progress = json.loads(progress_path.read_text(encoding="utf-8")) if progress_path.exists() else {}
    reviewed = list(draft)
    kept: list[int] = []
    for ci, (a, b) in enumerate(chunks):
        key = str(ci)
        if key in progress and len(progress[key]) == b - a:
            reviewed[a:b] = progress[key]
            continue
        expected = list(range(a + 1, b + 1))
        filtered, _ = filter_glossary("\n\n".join(src[a:b]), terms, gconfig)
        gblock = build_glossary_block(filtered, lang, meta)
        prev = reviewed[a - 1] if a > 0 else ""
        prev_block = f"# CONTEXT - previous revised paragraph (do not output it)\n\n{prev}\n\n" if prev else ""
        user = (f"{prev_block}{gblock}\n"
                f"# RUSSIAN SOURCE (paragraphs {expected[0]}-{expected[-1]})\n\n{numbered(src[a:b], a + 1)}\n\n"
                f"# {lang.upper()} DRAFT\n\n{numbered(draft[a:b], a + 1)}\n\n"
                f"Return the revised {lang} paragraphs {expected[0]}-{expected[-1]} now, "
                f"inside {TAG_IN} ... {TAG_OUT}, each preceded by its [[Pn]] marker.")
        result = None
        for attempt in range(2):
            prompt = user if attempt == 0 else user + RETRY_NOTE.format(markers=", ".join(f"[[P{n}]]" for n in expected))
            try:
                resp = await provider.generate(prompt, timeout=args.timeout, system_prompt=system_prompt(ed))
            except ClaudeUsageLimitError as e:
                raise UsageLimit(e.resets_at) from e
            except RateLimitError as e:
                raise UsageLimit(None) from e
            if resp and resp.content:
                result = parse_response(resp.content, expected)
                if result is not None:
                    break
            print(f"[pass2] {draft_path.name} chunk {ci + 1}/{len(chunks)}: unusable answer (attempt {attempt + 1})", flush=True)
        if result is None:
            print(f"[pass2] {draft_path.name} chunk {ci + 1}: keeping the draft for paragraphs {expected[0]}-{expected[-1]}", flush=True)
            kept.extend(expected)
            result = draft[a:b]
        reviewed[a:b] = result
        progress[key] = result
        progress_path.write_text(json.dumps(progress, ensure_ascii=False, indent=1), encoding="utf-8")
        changed = sum(1 for x, y in zip(draft[a:b], result) if x != y)
        print(f"[pass2] {draft_path.name} chunk {ci + 1}/{len(chunks)}: {changed}/{b - a} paragraphs changed", flush=True)
    out_path.write_text("\n\n".join(reviewed).rstrip() + "\n", encoding="utf-8")
    diff = difflib.unified_diff([p + "\n" for p in draft], [p + "\n" for p in reviewed],
                                fromfile=f"draft/{draft_path.name}", tofile=f"reviewed/{out_path.name}", lineterm="", n=0)
    Path(f"{out_path}.changes.diff").write_text("".join(diff), encoding="utf-8")
    total = sum(1 for x, y in zip(draft, reviewed) if x != y)
    print(f"[pass2] {out_path.name}: {total}/{len(src)} paragraphs revised" + (f"; draft kept for {kept}" if kept else ""), flush=True)
    return kept


def sleep_until(resets_at) -> None:
    import subprocess
    if resets_at:
        try:
            target = int(subprocess.run(["date", "-d", str(resets_at), "+%s"], capture_output=True, text=True, check=True).stdout)
            wait = target - int(time.time())
            if wait > 0:
                print(f"[pass2] usage limit: sleeping until {resets_at} (+90 s)", flush=True)
                time.sleep(wait + 90)
                return
        except (subprocess.CalledProcessError, ValueError):
            pass
    print("[pass2] usage limit: reset time unknown, sleeping 30 min", flush=True)
    time.sleep(1800)


async def run(args) -> int:
    cfg = edlib.load_config()
    ed = cfg.edition(args.code)
    rd = edlib.run_dir(ed.code, args.run or edlib.default_run_name(args.model))
    draft_dir, out_dir = rd / "draft", rd / "reviewed"
    if not draft_dir.exists():
        raise SystemExit(f"{edlib.rel(draft_dir)} does not exist: run pass1.py first (same --run/--model)")
    out_dir.mkdir(exist_ok=True)
    glossary = load_glossary_from_file(str(ed.glossary_path))
    provider = ClaudeCliProvider(model=args.model, delay_seconds=args.delay)
    kept_total = {}
    try:
        for src in edlib.export_source(cfg):
            if args.parts and src.name[:2] not in args.parts:
                continue
            draft, out = draft_dir / src.name, out_dir / src.name
            if Path(f"{out}.done").exists():
                continue
            if not Path(f"{draft}.done").exists():
                raise SystemExit(f"{src.name}: draft not finished (pass 1)")
            while True:
                try:
                    kept = await review_part(ed, provider, src, draft, out, glossary, args)
                    break
                except UsageLimit as e:
                    sleep_until(e.resets_at)
            if kept:
                kept_total[src.name] = kept
            Path(f"{out}.done").touch()
    finally:
        await provider.close()
    print(f"[pass2] run {edlib.rel(rd)} reviewed" + (f"; draft kept in {kept_total}" if kept_total else ""))
    return 0


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("code")
    ap.add_argument("--model", default="opus")
    ap.add_argument("--run", help="run name (default: <model>-<date>)")
    ap.add_argument("--delay", type=float, default=10.0)
    ap.add_argument("--parts", nargs="*")
    ap.add_argument("--timeout", type=int, default=900)
    ap.add_argument("--max-src-tokens", type=int, default=1100)
    ap.add_argument("--max-glossary-entries", type=int, default=60)
    args = ap.parse_args()
    sys.exit(asyncio.run(run(args)))


if __name__ == "__main__":
    main()
