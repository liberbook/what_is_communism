---
name: book-edition-translation
description: Add a new language edition of the booklet "Что такое коммунизм?" or retranslate an existing edition with a newer model, using this repository's scripted pipeline (languages.toml, tools/new_language.py, tools/glossary, tools/translate/run.py, tools/checks, tools/report). Use it whenever the user asks for a new translation (German, French, Spanish, ...), a better or newer translation of the English/Italian edition, a glossary for a language, a comparison of two translations or models, or to fix, check or rebuild an edition, even if they don't name the tools.
---

# Translating an edition of the booklet

The repository builds every edition (PDF A4/A5/booklet, EPUB, FB2, HTML,
Markdown) from LaTeX parts. The Russian edition in `russian/parts/` is the
source; every other edition is described in `languages.toml`. All the steps
are scripts in `tools/` (documented in `tools/README.md`), so the job is
mostly running them in order, reading their output, and handing the human
decisions to the user. Prefer the scripts over ad-hoc code: they resume after
interruptions and their checks are what CI runs.

## Ground rules

- **Model calls go through the official `claude` CLI on the user's
  subscription** (TranslateBooksWithLLMs' `claude-cli` provider). Never read,
  copy or print OAuth tokens, never use `--bare`, never run a proxy. Default
  pause between calls: 10 s (`--delay`); keep what the user asked for.
- **Nothing outside `work/` changes until `--promote`.** Run without it first,
  read the report, tell the user what you found, then promote.
- **Committed files are English** (code, comments, docs, commit messages).
  Commit or push only when the user asks; this repository's owner wants no
  `Co-Authored-By` trailer in commit messages.
- The usage limit of the subscription can stop a step. The scripts sleep
  until the reset and continue; if a command is interrupted, rerun the exact
  same command (same `--run`) and it resumes.

## New language

1. **Create the edition.** Pick the babel option and check it exists
   (`kpsewhich <babel>.ldf`); if it doesn't, tell the user which TeX Live
   package to install and add it to the `Dockerfile` so CI can build.
   ```bash
   python3 tools/new_language.py de --dir german --name Deutsch --english-name German \
       --title "Was ist Kommunismus?" --author "Gruppe Engels" --basename was_ist_kommunismus \
       --babel ngerman --read-online "Online lesen" --download Herunterladen \
       --print-label "PDF A5 zum Drucken" --booklet-label "Broschüre A4" \
       --credit "Aus dem Russischen übersetzt mit Claude Opus 5.5 und TranslateBooksWithLLMs"
   ```
2. **Set the language rules** in the new `[edition.typography]` and
   `[edition.prompt]` blocks of `languages.toml` (they are copied from English):
   quotation marks of both levels, dash style, number-range dash, number
   formatting, terms that must stay distinct, which editions are canonical for
   Marx/Engels/Lenin in that language. These drive both the reviewer prompt and
   the final typography, so get them right before translating.
3. **Draft the glossary**: `python3 tools/glossary/draft.py de`. It writes
   `glossary/targets.de.json` with `"status": "draft"` and `CHECK:` notes where
   the model was unsure.
4. **Glossary review is the user's step.** Show the user the `CHECK:` entries
   and anything you doubt (names, titles, canonical quotations). Apply their
   corrections, remove the notes, and set `"status": "reviewed"` only when they
   agree. `tools/glossary/build.py de` refuses a draft on purpose.
5. **Translate**: `python3 tools/translate/run.py de --delay 10` (about 150
   model calls for the whole book). It builds the glossary, translates, reviews,
   checks, prepares the final text and writes
   `work/de/<run>/report/index.html`.
6. **Read the report and the checks** (see below), summarise them for the user,
   then promote:
   `python3 tools/translate/run.py de --run <run> --promote`. This writes
   `german/parts/`, builds, runs every check, and regenerates `site/index.html`
   and the README tables.

## Retranslate with a new model

```bash
python3 tools/translate/run.py en --model <model-id> --run <short-name>
```
The report then compares the published edition (A) with the new run (B).
Compare old runs with
`python3 tools/report/report.py en --a run:<old>/final --b run:<new>/final --out work/en/cmp`.
Promote only if the user decides the new run is better.

## Reading the results

- `checks/structure.py` errors (paragraph or footnote counts, Cyrillic left,
  unescaped `%`, foreign quotation marks) must be fixed before promoting. An
  unescaped `%` silently deletes the rest of a paragraph in the PDF.
- `checks/glossary.py` lists targets missing per paragraph (`05§24` = part 05,
  paragraph 24). Below 90 % for concepts and names is a real problem;
  isolated misses in quotations are often legitimate rephrasing; check them in
  the report.
- Report flags (⚑) mark paragraphs with a missing glossary target, a suspicious
  length ratio, or a missing paragraph. Open those first.
- `finalize.py` warns about unbalanced quotes; a quotation that continues into
  the next paragraph is normal (compare with the Russian paragraph).
- The API's output filter occasionally blocks a chunk; the translator retries
  it. If a part keeps failing, run that part alone with `--parts NN`.

## Other tasks

- Change a term: edit `glossary/terms.json` (source, optional hand-listed
  `"forms"`) and every `glossary/targets.<code>.json`, then
  `python3 tools/glossary/build.py --all`.
- Fix a defect in the Russian source: edit `russian/parts/`, then check that
  every edition still matches it with `python3 tools/checks/structure.py`.
- Everything at once, as CI does: `./build.sh && python3 tools/checks/all.py`.
