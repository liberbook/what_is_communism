#!/usr/bin/env python3
"""Side-by-side HTML report for reading a translation by eye (no AI).

Three columns per paragraph: the Russian source, version A and version B,
with the words changed from A to B highlighted. Paragraphs where a glossary
target is missing in B, or whose length differs suspiciously from the source,
are flagged. One page per part plus an index with per-part counts.

Versions are given as:
  edition          the edition's current LaTeX parts (what is published)
  run:NAME/STAGE   a pipeline run, STAGE = draft | reviewed | final
  a directory      of simple-format text parts (NN_slug__pNNN.txt)

Usage:
  python3 tools/report/report.py en --run NAME            # draft vs reviewed of that run
  python3 tools/report/report.py en --a edition --b run:NAME/reviewed   # published vs new run
  python3 tools/report/report.py en --a run:OLD/reviewed --b run:NEW/reviewed --out work/en/cmp
The report is written to work/<code>/<run>/report/ (or --out) ; open index.html.
"""
from __future__ import annotations

import argparse
import difflib
import html
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "checks"))
import edlib  # noqa: E402
from glossary import source_regex, target_found, words  # noqa: E402

CSS = """
:root{color-scheme:light dark;--bg:#fbfbf9;--ink:#1b1b1b;--muted:#6b6b66;--line:#e2e0da;--card:#fff;--del:#fbe0dc;--delink:#9a2316;--ins:#dcf3df;--insink:#18622a;--flag:#b0301e}
@media (prefers-color-scheme:dark){:root{--bg:#151514;--ink:#e9e8e3;--muted:#a09f99;--line:#2f2e2b;--card:#1d1c1a;--del:#4a2320;--delink:#ffb4a8;--ins:#1f3d25;--insink:#a6e3b0;--flag:#ef7d68}}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--ink);font:15px/1.5 Georgia,"PT Serif",serif}
main{max-width:1500px;margin:0 auto;padding:24px 16px 64px}h1{font-size:1.4em;margin:0 0 4px}.sub{color:var(--muted);font:13px system-ui,sans-serif;margin:0 0 20px}
nav{font:13px system-ui,sans-serif;margin:0 0 16px}nav a{color:var(--muted);margin-right:12px}
.row{display:grid;grid-template-columns:3.2em 1fr 1fr 1fr;gap:12px;padding:10px 0;border-top:1px solid var(--line)}
.row.head{font:600 12px system-ui,sans-serif;text-transform:uppercase;letter-spacing:.06em;color:var(--muted);border:0}
.n{font:12px system-ui,sans-serif;color:var(--muted)}.n .f{display:block;color:var(--flag);font-weight:600;margin-top:4px}
.same{color:var(--muted)}del{background:var(--del);color:var(--delink);text-decoration:line-through}ins{background:var(--ins);color:var(--insink);text-decoration:none}
.flags{grid-column:2/5;font:12px system-ui,sans-serif;color:var(--flag)}
table{border-collapse:collapse;font:14px system-ui,sans-serif;width:100%}td,th{border-bottom:1px solid var(--line);padding:6px 8px;text-align:left}th{color:var(--muted);font-weight:600}
@media (max-width:900px){.row{grid-template-columns:1fr}.flags{grid-column:1}}
"""


def load_version(spec: str, ed: edlib.Edition, cfg: edlib.Config) -> tuple[str, list[list[str]]]:
    if spec == "edition":
        return f"{ed.dir}/parts (published)", edlib.edition_blocks(ed)
    if spec.startswith("run:"):
        name, _, stage = spec[4:].partition("/")
        d = edlib.run_dir(ed.code, name) / (stage or "reviewed")
        label = f"run {name} · {stage or 'reviewed'}"
    else:
        d, label = Path(spec), spec
    if not d.exists():
        raise SystemExit(f"{d} does not exist")
    blocks = []
    for p in edlib.source_txt_paths(cfg):
        f = d / p.name
        if not f.exists():
            slug_matches = list(d.glob(f"{p.name[:3]}*.txt"))
            f = slug_matches[0] if slug_matches else f
        blocks.append(edlib.read_text_blocks(f) if f.exists() else [])
    return label, blocks


def word_diff(a: str, b: str) -> tuple[str, int]:
    ta, tb = re.findall(r"\s+|[^\s]+", a), re.findall(r"\s+|[^\s]+", b)
    out, changed = [], 0
    for tag, i1, i2, j1, j2 in difflib.SequenceMatcher(None, ta, tb, autojunk=False).get_opcodes():
        if tag == "equal":
            out.append(html.escape("".join(ta[i1:i2])))
            continue
        changed += 1
        if i2 > i1:
            out.append(f"<del>{html.escape(''.join(ta[i1:i2]))}</del>")
        if j2 > j1:
            out.append(f"<ins>{html.escape(''.join(tb[j1:j2]))}</ins>")
    return "".join(out), changed


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("code")
    ap.add_argument("--run", help="pipeline run (default A/B: its draft and reviewed text)")
    ap.add_argument("--a", help="version A (see above)")
    ap.add_argument("--b", help="version B (see above)")
    ap.add_argument("--out", type=Path, help="output directory")
    args = ap.parse_args()
    cfg = edlib.load_config()
    ed = cfg.edition(args.code)
    a_spec = args.a or (f"run:{args.run}/draft" if args.run else None)
    b_spec = args.b or (f"run:{args.run}/reviewed" if args.run else None)
    if not (a_spec and b_spec):
        ap.error("give --run NAME, or --a and --b")
    out = args.out or (edlib.run_dir(ed.code, args.run) / "report" if args.run else edlib.WORK / ed.code / "report")
    out.mkdir(parents=True, exist_ok=True)
    a_label, A = load_version(a_spec, ed, cfg)
    b_label, B = load_version(b_spec, ed, cfg)
    S = edlib.edition_blocks(cfg.source)
    terms = []
    if ed.glossary_path and ed.glossary_path.exists():
        gl = json.loads(ed.glossary_path.read_text(encoding="utf-8"))
        terms = [(t, source_regex(t["source"].split("|"))) for t in gl["terms"]
                 if t["category"] in {"concept", "person", "place", "acronym", "organization", "event"}]
    titles = [p.stem for p in cfg.source.part_paths()]
    index_rows = []
    for k, (src, a, b) in enumerate(zip(S, A, B)):
        name = f"{k + 1:02d}"
        title = b[0] if b else titles[k]
        rows, n_changed, n_flags = [], 0, 0
        n = max(len(src), len(a), len(b))
        for i in range(n):
            s, x, y = (src[i] if i < len(src) else ""), (a[i] if i < len(a) else ""), (b[i] if i < len(b) else "")
            flags = []
            if y and terms:
                tw = words(y)
                missing = [t["target"] for t, rx in terms if rx.search(s) and not target_found(t["target"], tw)]
                if missing:
                    flags.append("glossary target not found: " + ", ".join(dict.fromkeys(missing)))
            if s and y and len(s) >= 80 and not 0.7 <= len(y) / len(s) <= 1.9:
                flags.append(f"length ratio {len(y) / len(s):.2f}")
            if not y:
                flags.append("paragraph missing in B")
            diff, c = word_diff(x, y)
            n_changed += c > 0
            n_flags += bool(flags)
            a_cell = f'<div class="same">{html.escape(x)}</div>' if c == 0 else f"<div>{html.escape(x)}</div>"
            b_cell = f'<div class="same">{html.escape(y)}</div>' if c == 0 else f"<div>{diff}</div>"
            flag_html = f'<div class="flags">⚑ {html.escape("; ".join(flags))}</div>' if flags else ""
            rows.append(f'<div class="row" id="p{i + 1}"><div class="n">§{i + 1}{"<span class=f>⚑</span>" if flags else ""}</div>'
                        f"<div>{html.escape(s)}</div>{a_cell}{b_cell}{flag_html}</div>")
        nav = f'<nav><a href="index.html">index</a>' + (f'<a href="{k:02d}.html">← {k:02d}</a>' if k else "") + \
              (f'<a href="{k + 2:02d}.html">{k + 2:02d} →</a>' if k + 1 < len(S) else "") + "</nav>"
        page = (f'<!doctype html><html lang="{ed.lang}"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">'
                f"<title>{name} {html.escape(title)}</title><style>{CSS}</style></head><body><main>{nav}"
                f"<h1>{name} · {html.escape(title)}</h1><p class=sub>{n_changed} of {n} paragraphs changed from A to B · {n_flags} flagged</p>"
                f'<div class="row head"><div>§</div><div>Russian source</div><div>A: {html.escape(a_label)}</div><div>B: {html.escape(b_label)} (changes)</div></div>'
                + "".join(rows) + "</main></body></html>")
        (out / f"{name}.html").write_text(page, encoding="utf-8")
        index_rows.append(f'<tr><td><a href="{name}.html">{name}</a></td><td>{html.escape(title)}</td><td>{n}</td><td>{n_changed}</td><td>{n_flags}</td></tr>')
    index = (f'<!doctype html><html lang="{ed.lang}"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">'
             f"<title>Review report · {ed.code}</title><style>{CSS}</style></head><body><main>"
             f"<h1>Review report · {html.escape(ed.english_name)} ({ed.code})</h1>"
             f"<p class=sub>A: {html.escape(a_label)} · B: {html.escape(b_label)} · ⚑ = glossary target missing in B, suspicious length, or missing paragraph</p>"
             "<table><tr><th>Part</th><th>Title</th><th>Paragraphs</th><th>Changed A→B</th><th>Flagged</th></tr>"
             + "".join(index_rows) + "</table></main></body></html>")
    (out / "index.html").write_text(index, encoding="utf-8")
    print(f"report written to {edlib.rel(out)}/index.html")


if __name__ == "__main__":
    main()
