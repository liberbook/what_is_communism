#!/usr/bin/env python3
"""Create a new translated edition and register it in languages.toml.

Creates <dir>/main.tex and <dir>/preamble.tex from tools/templates/, copies
the cover images, creates an empty <dir>/parts/, and appends an [[edition]]
block to languages.toml. Typography and review-prompt rules are copied from
the edition given with --like (default: en); edit them in languages.toml
before translating. The parts themselves are produced by the translation
pipeline (tools/translate/run.py).

Example:
  python3 tools/new_language.py de --dir german --name Deutsch --english-name German \\
      --title "Was ist Kommunismus?" --author "Gruppe Engels" --basename was_ist_kommunismus \\
      --babel ngerman --read-online "Online lesen" --download Herunterladen \\
      --print-label "PDF A5 zum Drucken" --booklet-label "Broschüre A4" --contents Inhalt \\
      --credit "Aus dem Russischen übersetzt mit Claude Opus 5.5 und TranslateBooksWithLLMs"
"""
from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from edlib import CONFIG, ROOT, latex_text, load_config  # noqa: E402

TEMPLATES = Path(__file__).resolve().parent / "templates"


def toml_str(v: str) -> str:
    return json.dumps(v, ensure_ascii=False)


def toml_list(vs: list[str]) -> str:
    return "[" + ", ".join(toml_str(v) for v in vs) + "]"


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("code", help="short language code, e.g. de")
    ap.add_argument("--dir", required=True, help="edition directory, e.g. german")
    ap.add_argument("--name", required=True, help="language name in the language itself, e.g. Deutsch")
    ap.add_argument("--english-name", required=True, help="language name in English, e.g. German")
    ap.add_argument("--title", required=True)
    ap.add_argument("--author", required=True)
    ap.add_argument("--basename", required=True, help="base name of the output files, ASCII")
    ap.add_argument("--babel", required=True, help="babel language option, e.g. ngerman, french, spanish")
    ap.add_argument("--fontenc", default="T1", help="fontenc encodings (T1 for Latin scripts, T1,T2A for Cyrillic)")
    ap.add_argument("--lang", help="BCP 47 tag for EPUB/HTML (default: the code)")
    ap.add_argument("--label", help="landing-page card label (default: --name)")
    ap.add_argument("--read-online", default="Read online")
    ap.add_argument("--download", default="Download")
    ap.add_argument("--print-label", default="PDF A5 for print")
    ap.add_argument("--booklet-label", default="A4 booklet")
    ap.add_argument("--about", default="", help="one-sentence description on the landing-page card")
    ap.add_argument("--contents", default="Contents", help="table-of-contents label on the landing-page card")
    ap.add_argument("--credit", default="", help="small line on the title page (optional)")
    ap.add_argument("--subject", default="Theory of communism", help="PDF subject metadata")
    ap.add_argument("--keywords", default="communism, Marxism, Marx, Engels, Lenin", help="PDF keywords metadata")
    ap.add_argument("--like", default="en", help="edition whose typography, prompt rules and part names are copied")
    args = ap.parse_args()

    cfg = load_config()
    if any(args.code == e.code or args.dir == e.dir for e in cfg.editions):
        raise SystemExit(f"edition {args.code} / {args.dir} already exists in languages.toml")
    like = cfg.edition(args.like)
    dest = ROOT / args.dir
    if dest.exists():
        raise SystemExit(f"{dest} already exists")

    ldf = subprocess.run(["kpsewhich", f"{args.babel}.ldf"], capture_output=True, text=True).stdout.strip()
    if not ldf:
        print(f"WARNING: babel language '{args.babel}' is not installed locally ({args.babel}.ldf not found). "
              f"Install the TeX Live language package, and add it to the Dockerfile so CI can build.")

    parts = list(like.parts)
    (dest / "parts").mkdir(parents=True)
    (dest / "parts" / ".gitkeep").write_text("", encoding="utf-8")
    shutil.copytree(cfg.source.src / "images", dest / "images")
    credit = rf"{{\small {latex_text(args.credit)}}}\\[0.4cm]" if args.credit else ""
    main_tex = (TEMPLATES / "main.tex").read_text(encoding="utf-8")
    main_tex = (main_tex.replace("@TITLE@", latex_text(args.title)).replace("@AUTHOR@", latex_text(args.author))
                .replace("@CREDIT@\n", credit + "\n" if credit else "")
                .replace("@PARTS@", "\n".join(rf"\subfile{{parts/{p}}}" for p in parts)))
    (dest / "main.tex").write_text(main_tex, encoding="utf-8")
    pre = (TEMPLATES / "preamble.tex").read_text(encoding="utf-8")
    for k, v in {"NAME": args.english_name, "BABEL": args.babel, "FONTENC": args.fontenc,
                 "TITLE": latex_text(args.title), "AUTHOR": latex_text(args.author),
                 "SUBJECT": latex_text(args.subject), "KEYWORDS": latex_text(args.keywords)}.items():
        pre = pre.replace(f"@{k}@", v)
    (dest / "preamble.tex").write_text(pre, encoding="utf-8")

    t, pr = like.typography, like.prompt
    ui = "\n".join(f"{k} = {toml_str(v)}" for k, v in like.ui.items())
    block = f"""
[[edition]]
code = {toml_str(args.code)}
english_name = {toml_str(args.english_name)}
dir = {toml_str(args.dir)}
lang = {toml_str(args.lang or args.code)}
name = {toml_str(args.name)}
label = {toml_str(args.label or args.name)}
title = {toml_str(args.title)}
author = {toml_str(args.author)}
basename = {toml_str(args.basename)}
read_online = {toml_str(args.read_online)}
download = {toml_str(args.download)}
files = {{ pdf = "PDF", print = {toml_str(args.print_label)}, booklet = {toml_str(args.booklet_label)} }}
about = {toml_str(args.about)}
contents = {toml_str(args.contents)}
target_language = {toml_str(args.english_name)}
glossary = {toml_str(f"{args.dir}/glossary.ru-{args.code}.json")}
parts = {toml_list(parts)}
[edition.ui]
# copied from the {like.code} edition: translate into {args.english_name}
{ui}
[edition.typography]
# copied from the {like.code} edition: set the conventions of {args.english_name}
quotes = {toml_list(t['quotes'])}
inner_quotes = {toml_list(t['inner_quotes'])}
dash = {toml_str(t['dash'])}
spaced_dash = {str(t['spaced_dash']).lower()}
range_dash = {toml_str(t['range_dash'])}
[edition.prompt]
# copied from the {like.code} edition: rewrite these rules for {args.english_name}
distinct = {toml_str(pr['distinct'])}
canon = {toml_str(pr['canon'])}
numbers = {toml_str(pr['numbers'])}
coinage = {toml_str(pr['coinage'])}
typography = {toml_str(pr['typography'])}
"""
    with CONFIG.open("a", encoding="utf-8") as f:
        f.write(block)
    load_config()  # validate
    print(f"created {dest.relative_to(ROOT)}/ and added edition {args.code} to languages.toml")
    print(f"""next steps:
  1. edit [edition.typography] and [edition.prompt] of {args.code} in languages.toml
  2. python3 tools/glossary/draft.py {args.code}        # draft glossary targets with the model
     then review glossary/targets.{args.code}.json and set "status": "reviewed"
  3. python3 tools/translate/run.py {args.code}          # translate, review, check, build, report
  4. python3 tools/render_docs.py                         # landing page and README tables""")


if __name__ == "__main__":
    main()
