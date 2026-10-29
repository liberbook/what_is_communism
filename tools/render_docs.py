#!/usr/bin/env python3
"""Generate the edition-dependent documents from languages.toml.

  site/index.html                      landing page (one card per edition)
  site/wake-up/index.html              entry page for readers of the article
                                       «Красная таблетка для материалиста»
  site/wake-up/<code>/index.html       per-language entry page: the red and blue
                                       pills (every edition listed in WAKE_TEXTS)
  README.md                            title line, languages badge and the
                                       blocks between <!-- editions:NAME:begin/end -->
  --site DIR                           also assemble the GitHub Pages site in DIR
                                       (site/ with its images + <code>/index.html from out/)

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
from edlib import ROOT, Config, Edition, load_config, read_part  # noqa: E402

STYLE = """  :root { color-scheme: light dark; --bg: #fdfdfb; --ink: #1a1a1a; --muted: #6a6a66; --line: #e4e2dc; --card: #ffffff; --accent: #b0301e; }
  @media (prefers-color-scheme: dark) { :root { --bg: #151514; --ink: #ecebe6; --muted: #a3a29c; --line: #2e2d2a; --card: #1d1c1a; --accent: #e0654e; } }
  * { box-sizing: border-box; }
  body { margin: 0; background: var(--bg); color: var(--ink); font: 17px/1.55 Georgia, "PT Serif", "Times New Roman", serif; }
  main { max-width: 860px; margin: 0 auto; padding: 56px 20px 64px; }
  .hero { display: grid; grid-template-columns: 150px 1fr; gap: 28px; align-items: center; margin: 0 0 44px; }
  .hero img { display: block; width: 100%; height: auto; border-radius: 4px; box-shadow: 0 12px 32px rgba(0, 0, 0, .22); }
  h1 { font-size: 2.1em; line-height: 1.15; margin: 0 0 8px; }
  .titles { color: var(--muted); margin: 0 0 14px; }
  .sub { color: var(--muted); margin: 0; font-family: system-ui, sans-serif; font-size: 15px; }
  .grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(300px, 1fr)); gap: 16px; }
  .card { background: var(--card); border: 1px solid var(--line); border-radius: 14px; padding: 22px; display: flex; flex-direction: column; gap: 14px; }
  .card h2 { margin: 0; font-size: 1.3em; }
  .about { margin: 0; font: 14px/1.5 system-ui, sans-serif; color: var(--muted); flex-grow: 1; }
  .lang { font: 600 12px system-ui, sans-serif; letter-spacing: .08em; text-transform: uppercase; color: var(--accent); }
  .read { display: inline-block; text-align: center; padding: 10px 14px; border-radius: 10px; background: var(--accent); color: #fff; text-decoration: none; font: 600 15px system-ui, sans-serif; }
  .read:hover { filter: brightness(1.08); }
  .files { display: flex; flex-wrap: wrap; gap: 6px 12px; font: 14px system-ui, sans-serif; }
  .files a { color: var(--muted); }
  details { border-top: 1px solid var(--line); padding-top: 10px; font: 14px/1.45 system-ui, sans-serif; }
  summary { cursor: pointer; color: var(--muted); }
  details ol { margin: 8px 0 0; padding-left: 1.5em; }
  details li { margin: 3px 0; }
  details a { color: var(--ink); text-decoration: none; }
  details a:hover { color: var(--accent); text-decoration: underline; }
  footer { margin-top: 48px; color: var(--muted); font: 13px/1.5 system-ui, sans-serif; }
  footer a { color: var(--muted); }
  @media (max-width: 560px) {
    main { padding-top: 32px; }
    .hero { grid-template-columns: 96px 1fr; gap: 18px; }
    h1 { font-size: 1.6em; }
  }"""


def dl(cfg: Config, name: str) -> str:
    return f"https://github.com/{cfg.data['repo']}/releases/latest/download/{name}"


def esc(s: str) -> str:
    return html.escape(s, quote=True)


def part_titles(ed: Edition) -> list[tuple[str, str]]:
    """(slug, title) of every part, or [] while some part is still missing."""
    paths = ed.part_paths()
    if not all(p.exists() for p in paths):
        return []
    return [(p.stem, read_part(p).title) for p in paths]


def social_meta(title: str, description: str, url: str, image: str, lang: str) -> str:
    locale = {"ru": "ru_RU", "uk": "uk_UA", "it": "it_IT", "en": "en_GB"}.get(lang, lang)
    return f"""<meta name="description" content="{esc(description)}">
<link rel="canonical" href="{url}">
<meta property="og:type" content="website">
<meta property="og:title" content="{esc(title)}">
<meta property="og:description" content="{esc(description)}">
<meta property="og:url" content="{url}">
<meta property="og:image" content="{image}">
<meta property="og:image:width" content="1200">
<meta property="og:image:height" content="630">
<meta property="og:locale" content="{locale}">
<meta name="twitter:card" content="summary_large_image">"""


def render_site(cfg: Config) -> str:
    src = cfg.source
    site = cfg.data["site"]
    e = lambda s: html.escape(s, quote=False)
    titles = " · ".join(dict.fromkeys(ed.title for ed in cfg.editions))
    others = " · ".join(dict.fromkeys(ed.title for ed in cfg.editions if ed.title != src.title))
    names = " · ".join(ed.name for ed in cfg.editions)
    cards = []
    for ed in cfg.editions:
        b = ed.basename
        f = ed.files
        about = f'\n      <p class="about">{e(ed.about)}</p>' if ed.get("about") else ""
        toc = part_titles(ed)
        contents = ""
        if toc:
            items = "\n".join(f'          <li><a href="{ed.code}/#sec:{slug}">{e(t)}</a></li>' for slug, t in toc)
            contents = f"""
      <details>
        <summary>{e(ed.get('contents', 'Contents'))}</summary>
        <ol>
{items}
        </ol>
      </details>"""
        cards.append(f"""    <section class="card" lang="{ed.lang}">
      <span class="lang">{e(ed.label)}</span>
      <h2>{e(ed.title)}</h2>{about}
      <a class="read" href="{ed.code}/">{e(ed.read_online)}</a>
      <div class="files">
        <a href="{dl(cfg, b + '.pdf')}">{e(f['pdf'])}</a>
        <a href="{dl(cfg, b + '_print.pdf')}">{e(f['print'])}</a>
        <a href="{dl(cfg, b + '_booklet_a4.pdf')}">{e(f['booklet'])}</a>
        <a href="{dl(cfg, b + '.epub')}">EPUB</a>
        <a href="{dl(cfg, b + '.fb2')}">FB2</a>
      </div>{contents}
    </section>""")
    repo = f"https://github.com/{cfg.data['repo']}"
    description = f"{src.author}. {src.get('about', '')} {names}: PDF, EPUB, FB2.".replace("  ", " ")
    return f"""<!doctype html>
<html lang="{src.lang}">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{e(titles)}</title>
{social_meta(src.title, description, site, site + "og.jpg", src.lang)}
<link rel="icon" href="favicon.svg" type="image/svg+xml">
<style>
{STYLE}
</style>
</head>
<body>
<main>
  <header class="hero">
    <img src="cover.jpg" width="420" height="594" alt="{esc(src.title)}">
    <div>
      <h1>{e(src.title)}</h1>
      <p class="titles">{e(others)}</p>
      <p class="sub">{e(src.author)}</p>
    </div>
  </header>
  <div class="grid">
{chr(10).join(cards)}
  </div>
  <footer>Исходники · Source: <a href="{repo}">{repo.removeprefix('https://')}</a> · <a href="{repo}/releases">релизы · releases</a></footer>
</main>
</body>
</html>
"""


# --- /wake-up/: the entry page for readers of «Красная таблетка для материалиста» ---

WAKE_STYLE = """  :root { color-scheme: dark; --bg: #0d1117; --bar: #21262d; --ink: #e6edf3; --dim: #8b949e; --line: #30363d;
          --green: #3fb950; --green-dk: #00a33a; --red: #d1242f; }
  * { box-sizing: border-box; }
  html { background: var(--bg); }
  body { margin: 0; background: var(--bg); color: var(--ink); font: 15px/1.65 "JetBrains Mono", ui-monospace, "SF Mono", Menlo, Consolas, "DejaVu Sans Mono", monospace; }
  #rain { position: fixed; inset: 0; width: 100%; height: 100%; opacity: .13; pointer-events: none; }
  .page { position: relative; max-width: 820px; margin: 0 auto; padding: 18px 16px 56px; }
  .marks { display: flex; justify-content: space-between; gap: 12px; font-size: 12px; color: var(--dim); margin-bottom: 28px; }
  .marks span:last-child { color: var(--green-dk); }
  .term { background: rgba(13, 17, 23, .94); border: 1px solid var(--line); border-radius: 6px 6px 2px 2px; overflow: hidden; box-shadow: 0 20px 60px rgba(0, 0, 0, .5); }
  .bar { position: relative; background: var(--bar); height: 38px; display: flex; align-items: center; justify-content: flex-end; gap: 6px; padding: 0 8px; border-bottom: 1px solid #000; }
  .bar b { position: absolute; left: 0; right: 0; text-align: center; font: 700 13px/38px system-ui, "Cantarell", "Ubuntu", sans-serif; color: #c9d1d9; pointer-events: none; }
  .bar i { position: relative; width: 24px; height: 24px; border-radius: 50%; background: #30363d; }
  .bar i::before, .bar i::after { content: ""; position: absolute; background: #c9d1d9; }
  .bar .min::before { left: 8px; right: 8px; top: 15px; height: 1.5px; }
  .bar .min::after { display: none; }
  .bar .max::before { left: 8px; top: 8px; width: 8px; height: 8px; background: none; border: 1.5px solid #c9d1d9; box-sizing: border-box; }
  .bar .max::after { display: none; }
  .bar .close::before, .bar .close::after { left: 7px; right: 7px; top: 11.25px; height: 1.5px; transform: rotate(45deg); }
  .bar .close::after { transform: rotate(-45deg); }
  .screen { padding: 22px 22px 26px; }
  :where(.screen p) { margin: 0; }
  .ps { color: var(--green); font-weight: 700; }
  .path { color: #58a6ff; font-weight: 700; }
  #scene { min-height: 1.5em; margin: 0; font-size: 1.35em; line-height: 1.5; white-space: pre-wrap; }
  .cursor { display: inline-block; width: .6em; height: 1.1em; vertical-align: -.15em; background: var(--green); animation: blink 1.1s steps(1) infinite; }
  @keyframes blink { 50% { opacity: 0; } }
  .cmd { margin: 30px 0 10px; }
  .ls { list-style: none; margin: 0; padding: 0; border-top: 1px dashed var(--line); }
  .ls li { display: grid; grid-template-columns: auto 2.4em 1fr auto; align-items: baseline; gap: 4px 14px; padding: 12px 0; border-bottom: 1px dashed var(--line); }
  .perm, .code { color: var(--dim); }
  .title { color: var(--ink); text-decoration: none; font-weight: 700; }
  .title:hover { color: var(--green); }
  .get { grid-column: 3 / -1; font-size: 13px; color: var(--dim); }
  .get a { color: var(--dim); }
  .get a:hover { color: var(--green); }
  .pill { display: inline-flex; align-items: center; gap: 8px; padding: 6px 14px; border-radius: 999px; font-family: inherit; font-size: 13px; font-weight: 700; line-height: 1;
          color: #fff; text-decoration: none; white-space: nowrap; border: 0; cursor: pointer; transition: transform .15s, box-shadow .15s; }
  .pill.red { background: var(--red); box-shadow: 0 0 0 0 rgba(209, 36, 47, .6); }
  .pill.red:hover, .pill.red:focus-visible { transform: translateY(-1px); box-shadow: 0 0 18px 2px rgba(209, 36, 47, .55); }
  :focus-visible { outline: 2px solid var(--green); outline-offset: 3px; }
  .choice { display: grid; grid-template-columns: 1fr 1fr; gap: 18px; margin-top: 36px; transition: opacity .8s; }
  .choice.later { opacity: 0; visibility: hidden; }
  .capsule { display: flex; flex-direction: column; align-items: center; justify-content: center; gap: 6px; min-height: 88px; padding: 16px 28px;
             border: 0; border-radius: 999px; color: #fff; font-family: inherit; font-size: 17px; font-weight: 700; line-height: 1.25; text-align: center;
             text-decoration: none; cursor: pointer; transition: transform .15s, box-shadow .15s, opacity .8s; }
  .capsule small { font-size: 12px; font-weight: 400; opacity: .85; }
  .capsule.red { background: radial-gradient(90% 70% at 30% 18%, rgba(255, 255, 255, .42), transparent 45%), linear-gradient(#e5383b, #8f0a12);
                 box-shadow: inset 0 -7px 14px rgba(0, 0, 0, .35), 0 8px 26px rgba(209, 36, 47, .35); }
  .capsule.blue { background: radial-gradient(90% 70% at 30% 18%, rgba(255, 255, 255, .42), transparent 45%), linear-gradient(#3a86ff, #0b3d91);
                  box-shadow: inset 0 -7px 14px rgba(0, 0, 0, .35), 0 8px 26px rgba(58, 134, 255, .3); }
  .capsule:hover, .capsule:focus-visible { transform: translateY(-2px); }
  .capsule.red:hover, .capsule.red:focus-visible { box-shadow: inset 0 -7px 14px rgba(0, 0, 0, .35), 0 0 30px 4px rgba(209, 36, 47, .6); }
  .capsule.blue:hover, .capsule.blue:focus-visible { box-shadow: inset 0 -7px 14px rgba(0, 0, 0, .35), 0 0 30px 4px rgba(58, 134, 255, .5); }
  .pills { position: relative; min-height: 100vh; min-height: 100svh; display: grid; place-items: center; padding: 24px 16px; }
  .pills .choice { width: min(760px, 100%); margin: 0; animation: appear 1.2s ease-out both; }
  @keyframes appear { from { opacity: 0; } }
  @media (max-width: 600px) {
    body { font-size: 14px; }
    .screen { padding: 18px 16px 22px; }
    #scene { font-size: 1.15em; }
    .ls li { grid-template-columns: 2.2em 1fr; }
    .ls .perm { display: none; }
    .ls .pill { grid-column: 2; justify-self: start; }
    .get { grid-column: 2; }
    .choice { grid-template-columns: 1fr; }
  }
  @media (prefers-reduced-motion: reduce) { .cursor { animation: none; } #rain { display: none; } .pill, .choice, .capsule { transition: none; } .pills .choice { animation: none; } }"""

# Matrix rain behind the page.
RAIN_SCRIPT = r"""  (() => {
    const c = document.getElementById("rain");
    if (still || !c.getContext) return;
    const g = c.getContext("2d"), glyphs = "アカサタナハマヤラワ01ДИАЛЕКТИКАПРАКСИС=+*<>".split("");
    let cols = [], size = 16;
    const fit = () => { c.width = innerWidth; c.height = innerHeight; cols = Array(Math.ceil(c.width / size)).fill(0).map(() => Math.random() * -50); };
    fit(); addEventListener("resize", fit);
    setInterval(() => {
      if (document.hidden) return;
      g.fillStyle = "rgba(13,17,23,.12)"; g.fillRect(0, 0, c.width, c.height);
      g.fillStyle = "#3fb950"; g.font = size + "px monospace";
      cols.forEach((y, i) => {
        g.fillText(glyphs[(Math.random() * glyphs.length) | 0], i * size, y * size);
        cols[i] = y * size > c.height && Math.random() > .975 ? 0 : y + 1;
      });
    }, 70);
  })();"""

# The film's lines, typed one after another; with JavaScript off or reduced
# motion the first one simply stays on screen.
WAKE_SCRIPT = r"""(() => {
  const still = matchMedia("(prefers-reduced-motion: reduce)").matches;
  const scene = document.getElementById("scene");
  const text = scene.querySelector(".text");
  const lines = ["Wake up, Neo…", "The Matrix has you…", "Follow the white rabbit.", "Knock, knock, Neo."];
  const wait = ms => new Promise(r => setTimeout(r, ms));
  if (!still) (async () => {
    for (const [i, line] of lines.entries()) {
      text.textContent = "";
      for (const ch of line) { text.textContent += ch; await wait(ch === " " ? 40 : 55 + Math.random() * 70); }
      if (i < lines.length - 1) await wait(1900);
    }
  })();
""" + RAIN_SCRIPT + """
})();"""

# /wake-up/<code>/: just the two pills over the rain. The red one leads to the
# book; the blue one makes both pills fade away until the page is reloaded.
WAKE_LANG_SCRIPT = r"""(() => {
  const still = matchMedia("(prefers-reduced-motion: reduce)").matches;
  const choice = document.getElementById("choice");
""" + RAIN_SCRIPT + r"""
  document.getElementById("blue").addEventListener("click", () => {
    choice.classList.add("later");
  });
})();"""


def render_wake_up(cfg: Config) -> str:
    src = cfg.source
    site = cfg.data["site"]
    url = site + "wake-up/"
    e = lambda s: html.escape(s, quote=False)
    rows = []
    for ed in cfg.editions:
        b = ed.basename
        f = ed.files
        links = " · ".join(f'<a href="{dl(cfg, name)}" title="{esc(label)}">{tag}</a>' for tag, name, label in [
            ("pdf", b + ".pdf", f["pdf"]), ("a5", b + "_print.pdf", f["print"]), ("a4", b + "_booklet_a4.pdf", f["booklet"]),
            ("epub", b + ".epub", "EPUB"), ("fb2", b + ".fb2", "FB2")])
        rows.append(f"""        <li lang="{ed.lang}">
          <span class="perm">-r--r--r--</span><span class="code">{ed.code}</span>
          <a class="title" href="../{ed.code}/">{e(ed.title)}</a>
          <a class="pill red" href="../{ed.code}/">{e(ed.read_online.lower())}</a>
          <span class="get">{links}</span>
        </li>""")
    title = f"Wake up, Neo… · {src.title}"
    description = ("Продолжение статьи «Красная таблетка для материалиста»: от Беркли и Гольбаха через Дидро к Марксу. "
                   f"Брошюра «{src.title}» — {src.author}.")
    return f"""<!doctype html>
<html lang="{src.lang}">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{e(title)}</title>
{social_meta(title, description, url, url + "og.png", src.lang)}
<meta name="theme-color" content="#0d1117">
<link rel="icon" href="../favicon.svg" type="image/svg+xml">
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@400;700&amp;display=swap">
<style>
{WAKE_STYLE}
</style>
</head>
<body>
<canvas id="rain" aria-hidden="true"></canvas>
<div class="page">
  <div class="marks" aria-hidden="true"><span>// there is no spoon</span><span>[praxis]</span></div>
  <main class="term">
    <div class="bar" aria-hidden="true"><b>neo@matrix: ~</b><i class="min"></i><i class="max"></i><i class="close"></i></div>
    <div class="screen">
      <p id="scene" aria-live="polite"><span class="text">Wake up, Neo…</span><span class="cursor" aria-hidden="true"></span></p>

      <p class="cmd"><span class="ps">neo@matrix</span>:<span class="path">~</span>$ ls -l ~/red-pill/</p>
      <ul class="ls">
{chr(10).join(rows)}
      </ul>


    </div>
  </main>
</div>
<script>
{WAKE_SCRIPT}
</script>
</body>
</html>
"""


def render_wake_up_lang(cfg: Config, ed: Edition) -> str:
    site = cfg.data["site"]
    url = site + f"wake-up/{ed.code}/"
    e = lambda s: html.escape(s, quote=False)
    t = WAKE_TEXTS[ed.code]
    title = f"{t['wake']} · {ed.title}"
    description = t["description"].format(title=ed.title, author=ed.author)
    return f"""<!doctype html>
<html lang="{ed.lang}">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{e(title)}</title>
{social_meta(title, description, url, site + "wake-up/og.png", ed.lang)}
<meta name="theme-color" content="#0d1117">
<link rel="icon" href="../../favicon.svg" type="image/svg+xml">
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@400;700&amp;display=swap">
<style>
{WAKE_STYLE}
</style>
</head>
<body>
<canvas id="rain" aria-hidden="true"></canvas>
<main class="pills">
  <div class="choice" id="choice">
    <a class="capsule red" href="../../{ed.code}/">{e(ed.title)}</a>
    <button class="capsule blue" id="blue" type="button">{e(t['blue'])}</button>
  </div>
</main>
<script>
{WAKE_LANG_SCRIPT}
</script>
</body>
</html>
"""


# Texts of the per-language pill pages, keyed by edition code. The description
# takes {title} and {author} of that edition.
WAKE_TEXTS = {
    "ru": {
        "wake": "Проснись, Нео…",
        "description": "Продолжение статьи «Красная таблетка для материалиста». Красная таблетка — "
                       "брошюра «{title}» ({author}), синяя — верить во что хочешь.",
        "blue": "Верить во что хочешь",
    },
    "it": {
        "wake": "Svegliati, Neo…",
        "description": "Seguito dell'articolo «La pillola rossa per il materialista». La pillola rossa è "
                       "l'opuscolo «{title}» ({author}), quella blu è credere in quello che vuoi.",
        "blue": "Credere in quello che vuoi",
    },
    "en": {
        "wake": "Wake up, Neo…",
        "description": "A sequel to the article “The Red Pill for the Materialist”. The red pill is "
                       "the booklet “{title}” ({author}); the blue one is believing whatever you like.",
        "blue": "Believe whatever you like",
    },
}


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


def wake_up_editions(cfg: Config) -> list[Edition]:
    return [ed for ed in cfg.editions if ed.code in WAKE_TEXTS]


def assemble_site(cfg: Config, dest: Path) -> None:
    shutil.copytree(ROOT / "site", dest, dirs_exist_ok=True)
    (dest / "index.html").write_text(render_site(cfg), encoding="utf-8")
    (dest / "wake-up" / "index.html").write_text(render_wake_up(cfg), encoding="utf-8")
    for ed in wake_up_editions(cfg):
        (dest / "wake-up" / ed.code).mkdir(exist_ok=True)
        (dest / "wake-up" / ed.code / "index.html").write_text(render_wake_up_lang(cfg, ed), encoding="utf-8")
    for ed in cfg.editions:
        src = ROOT / "out" / ed.dir / f"{ed.basename}.html"
        if not src.exists():
            raise SystemExit(f"missing {src}: build the editions first")
        (dest / ed.code).mkdir(exist_ok=True)
        shutil.copy2(src, dest / ed.code / "index.html")
    print(f"site assembled in {dest}: {', '.join(ed.code for ed in cfg.editions)}")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--check", action="store_true", help="exit 1 if the site pages or README.md are out of date")
    ap.add_argument("--site", type=Path, help="assemble the GitHub Pages site in this directory")
    args = ap.parse_args()
    cfg = load_config()
    targets = {
        ROOT / "site" / "index.html": render_site(cfg),
        ROOT / "site" / "wake-up" / "index.html": render_wake_up(cfg),
        ROOT / "README.md": render_readme(cfg, (ROOT / "README.md").read_text(encoding="utf-8")),
    }
    for ed in wake_up_editions(cfg):
        targets[ROOT / "site" / "wake-up" / ed.code / "index.html"] = render_wake_up_lang(cfg, ed)
    stale = [p for p, t in targets.items() if not p.exists() or p.read_text(encoding="utf-8") != t]
    if args.check:
        for p in stale:
            print(f"out of date: {p.relative_to(ROOT)} (run python3 tools/render_docs.py)")
        if stale:
            sys.exit(1)
        print("site pages and README.md are up to date")
    else:
        for p in stale:
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text(targets[p], encoding="utf-8")
            print(f"updated {p.relative_to(ROOT)}")
    if args.site:
        assemble_site(cfg, args.site)


if __name__ == "__main__":
    main()
