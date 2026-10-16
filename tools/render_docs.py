#!/usr/bin/env python3
"""Generate the edition-dependent documents from languages.toml.

  site/index.html                      landing page (one card per edition)
  README.md                            title line, languages badge and the
                                       blocks between <!-- editions:NAME:begin/end -->
  --site DIR                           also assemble the GitHub Pages site in DIR
                                       (index.html + <code>/index.html from out/)

Usage:
  python3 tools/render_docs.py            # rewrite site/index.html and README.md
  python3 tools/render_docs.py --check    # exit 1 if they are out of date
  python3 tools/render_docs.py --site _site
"""
from __future__ import annotations

import argparse
import html
import re
import shutil
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from edlib import ROOT, Config, load_config  # noqa: E402

STYLE = """  :root { color-scheme: light dark; --bg: #fdfdfb; --ink: #1a1a1a; --muted: #6a6a66; --line: #e4e2dc; --card: #ffffff; --accent: #b0301e; }
  @media (prefers-color-scheme: dark) { :root { --bg: #151514; --ink: #ecebe6; --muted: #a3a29c; --line: #2e2d2a; --card: #1d1c1a; --accent: #e0654e; } }
  * { box-sizing: border-box; }
  body { margin: 0; background: var(--bg); color: var(--ink); font: 17px/1.55 Georgia, "PT Serif", "Times New Roman", serif; }
  main { max-width: 860px; margin: 0 auto; padding: 56px 20px 64px; }
  h1 { font-size: 2.1em; line-height: 1.15; margin: 0 0 8px; }
  .sub { color: var(--muted); margin: 0 0 40px; font-family: system-ui, sans-serif; font-size: 15px; }
  .grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(240px, 1fr)); gap: 16px; }
  .card { background: var(--card); border: 1px solid var(--line); border-radius: 14px; padding: 22px; display: flex; flex-direction: column; gap: 14px; }
  .card h2 { margin: 0; font-size: 1.3em; }
  .lang { font: 600 12px system-ui, sans-serif; letter-spacing: .08em; text-transform: uppercase; color: var(--accent); }
  .read { display: inline-block; text-align: center; padding: 10px 14px; border-radius: 10px; background: var(--accent); color: #fff; text-decoration: none; font: 600 15px system-ui, sans-serif; }
  .files { display: flex; flex-wrap: wrap; gap: 6px 12px; font: 14px system-ui, sans-serif; }
  .files a { color: var(--muted); }
  footer { margin-top: 48px; color: var(--muted); font: 13px/1.5 system-ui, sans-serif; }
  footer a { color: var(--muted); }"""


def dl(cfg: Config, name: str) -> str:
    return f"https://github.com/{cfg.data['repo']}/releases/latest/download/{name}"


def render_site(cfg: Config) -> str:
    src = cfg.source
    e = lambda s: html.escape(s, quote=False)
    titles = " · ".join(dict.fromkeys(ed.title for ed in cfg.editions))
    names = " · ".join(ed.name for ed in cfg.editions)
    cards = []
    for ed in cfg.editions:
        b = ed.basename
        f = ed.files
        cards.append(f"""    <section class="card" lang="{ed.lang}">
      <span class="lang">{e(ed.label)}</span>
      <h2>{e(ed.title)}</h2>
      <a class="read" href="{ed.code}/">{e(ed.read_online)}</a>
      <div class="files">
        <a href="{dl(cfg, b + '.pdf')}">{e(f['pdf'])}</a>
        <a href="{dl(cfg, b + '_print.pdf')}">{e(f['print'])}</a>
        <a href="{dl(cfg, b + '_booklet_a4.pdf')}">{e(f['booklet'])}</a>
        <a href="{dl(cfg, b + '.epub')}">EPUB</a>
        <a href="{dl(cfg, b + '.fb2')}">FB2</a>
      </div>
    </section>""")
    repo = f"https://github.com/{cfg.data['repo']}"
    return f"""<!doctype html>
<html lang="{src.lang}">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{e(titles)}</title>
<meta name="description" content="Брошюра «{e(src.title)}»: читать онлайн, скачать PDF, EPUB, FB2 — {e(names)}.">
<style>
{STYLE}
</style>
</head>
<body>
<main>
  <h1>{e(src.title)}</h1>
  <p class="sub">{e(src.author)} — брошюра о коммунизме как научной теории понимания и преобразования общества.</p>
  <div class="grid">
{chr(10).join(cards)}
  </div>
  <footer>Исходники и все версии: <a href="{repo}">{repo.removeprefix('https://')}</a> · <a href="{repo}/releases">релизы</a></footer>
</main>
</body>
</html>
"""


def readme_blocks(cfg: Config) -> dict[str, str]:
    site = cfg.data["site"]
    eds = cfg.editions
    links = " · ".join(f"[{ed.name}]({site}{ed.code}/)" for ed in eds)
    rows = []
    for ed in eds:
        b = ed.basename
        rows.append(f"| **{ed.name}** — {ed.title} | [PDF]({dl(cfg, b + '.pdf')}) | [PDF]({dl(cfg, b + '_print.pdf')}) "
                    f"| [PDF]({dl(cfg, b + '_booklet_a4.pdf')}) | [EPUB]({dl(cfg, b + '.epub')}) | [FB2]({dl(cfg, b + '.fb2')}) |")
    releases = f"https://github.com/{cfg.data['repo']}/releases"
    downloads = f"""## {' · '.join(dict.fromkeys(ed.read_online for ed in eds))}

{links} — или главная страница: [{site.removeprefix('https://')}]({site})

## {' · '.join(dict.fromkeys(ed.download for ed in eds))}

| | Читать с экрана (A4) | Печать (A5) | Брошюра на A4 (двусторонняя печать) | EPUB | FB2 |
|---|---|---|---|---|---|
{chr(10).join(rows)}

Все версии — в [релизах]({releases}). Every version: [Releases]({releases})."""
    results = ("The same files are also in [`results/`](results/) (Markdown and HTML versions too, readable right on GitHub: "
               + " · ".join(f"[{ed.code.upper()}](results/{ed.dir}/{ed.basename}.md)" for ed in eds) + ").")
    count = ["zero", "one", "two", "three", "four", "five", "six", "seven", "eight", "nine", "ten"]
    n = len(eds)
    lst = [f"This repository contains {count[n] if n < len(count) else n} compact LaTeX editions of the same political-theoretical booklet:", ""]
    for ed in eds:
        extra = f" (the original, by «{ed.author}»)" if ed.is_source else ""
        lst.append(f"- `{ed.dir}/` — {ed.english_name} edition{extra}: **{ed.title}**")
    return {"downloads": downloads, "results": results, "list": "\n".join(lst)}


def render_readme(cfg: Config, text: str) -> str:
    for name, body in readme_blocks(cfg).items():
        pat = re.compile(rf"(<!-- editions:{name}:begin -->\n).*?(\n<!-- editions:{name}:end -->)", re.S)
        if not pat.search(text):
            raise SystemExit(f"README.md: markers for block {name!r} are missing")
        text = pat.sub(lambda m: m.group(1) + body + m.group(2), text)
    codes = "%20%C2%B7%20".join(ed.code for ed in cfg.editions)
    text = re.sub(r"(!\[Languages\]\(https://img\.shields\.io/badge/languages-)[^)]*?(-c0392b\))", rf"\g<1>{codes}\g<2>", text)
    titles = " / ".join(dict.fromkeys(["What is communism?"] + [ed.title for ed in cfg.editions if ed.lang != "en"]))
    text = re.sub(r"\A# [^\n]*", f"# {titles}", text)
    return text


def assemble_site(cfg: Config, dest: Path) -> None:
    dest.mkdir(parents=True, exist_ok=True)
    (dest / "index.html").write_text(render_site(cfg), encoding="utf-8")
    for ed in cfg.editions:
        src = ROOT / "out" / ed.dir / f"{ed.basename}.html"
        if not src.exists():
            raise SystemExit(f"missing {src}: build the editions first")
        (dest / ed.code).mkdir(exist_ok=True)
        shutil.copy2(src, dest / ed.code / "index.html")
    print(f"site assembled in {dest}: {', '.join(ed.code for ed in cfg.editions)}")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--check", action="store_true", help="exit 1 if site/index.html or README.md is out of date")
    ap.add_argument("--site", type=Path, help="assemble the GitHub Pages site in this directory")
    args = ap.parse_args()
    cfg = load_config()
    targets = {
        ROOT / "site" / "index.html": render_site(cfg),
        ROOT / "README.md": render_readme(cfg, (ROOT / "README.md").read_text(encoding="utf-8")),
    }
    stale = [p for p, t in targets.items() if p.read_text(encoding="utf-8") != t]
    if args.check:
        for p in stale:
            print(f"out of date: {p.relative_to(ROOT)} (run python3 tools/render_docs.py)")
        if stale:
            sys.exit(1)
        print("site/index.html and README.md are up to date")
    else:
        for p in stale:
            p.write_text(targets[p], encoding="utf-8")
            print(f"updated {p.relative_to(ROOT)}")
    if args.site:
        assemble_site(cfg, args.site)


if __name__ == "__main__":
    main()
