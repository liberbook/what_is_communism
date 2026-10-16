# Tools: editions, glossary, translation, checks

Everything that depends on the language is described in
[`languages.toml`](../languages.toml); the tools read it. The model is used
only to draft glossary targets and to translate and review; every check is
deterministic and needs no AI.

| Tool | What it does |
|------|--------------|
| `new_language.py CODE --dir ... --name ... --title ...` | creates `<dir>/` (main.tex, preamble.tex, images) from `templates/` and appends the edition to `languages.toml` |
| `glossary/draft.py CODE` | asks the model for the targets of every term in `glossary/terms.json` → `glossary/targets.CODE.json` with `"status": "draft"` |
| `glossary/build.py CODE … \| --all` | builds the edition's glossary (Russian inflected forms found in the text); refuses a draft |
| `translate/run.py CODE` | the whole cycle below, resumable; `--promote` writes the edition |
| `translate/pass1.py`, `pass2.py`, `finalize.py` | the single steps (translation, bilingual review, typography and LaTeX import) |
| `checks/structure.py` | paragraphs, footnotes, Cyrillic leftovers, LaTeX specials, quotation marks |
| `checks/glossary.py` | glossary targets present in the translated paragraphs |
| `checks/build.py` | every output exists, LaTeX errors, titles in the PDF, EPUB/FB2/HTML language |
| `checks/all.py` | all of the above plus `render_docs.py --check`; CI runs it after the build |
| `report/report.py CODE --run NAME` / `--a X --b Y` | side-by-side HTML (Russian, A, B with changes highlighted, flagged paragraphs) |
| `render_docs.py` | regenerates `site/index.html` and the edition blocks of the main README; `--site DIR` assembles GitHub Pages |

Requirements: Python 3.11+, the TeX Live / pandoc / poppler toolchain of the
main README, and for the model steps
[TranslateBooksWithLLMs](https://github.com/hydropix/TranslateBooksWithLLMs)
with its venv in `~/work/TranslateBooksWithLLMs` (or `TBL_ROOT`) and a logged-in
`claude` CLI (Claude subscription; no API key). The model steps re-run
themselves under that venv automatically.

Work files go to `work/` (gitignored): `work/source/` (the Russian parts as
text) and one directory per run, `work/<code>/<run>/` with `draft/`,
`reviewed/` (+ `.changes.diff`), `final/`, `report/`, `logs/` and `run.json`.

## Add a language

```bash
python3 tools/new_language.py de --dir german --name Deutsch --english-name German \
    --title "Was ist Kommunismus?" --author "Gruppe Engels" --basename was_ist_kommunismus \
    --babel ngerman --read-online "Online lesen" --download Herunterladen \
    --print-label "PDF A5 zum Drucken" --booklet-label "Broschüre A4" \
    --credit "Aus dem Russischen übersetzt mit Claude Opus 5.5 und TranslateBooksWithLLMs"
#  edit [edition.typography] and [edition.prompt] of "de" in languages.toml
#  if the babel language is missing: install the TeX Live package and add it to the Dockerfile
python3 tools/glossary/draft.py de                 # ~7 model calls
#  review glossary/targets.de.json by hand: fix targets, resolve every "CHECK:" note,
#  then set "status": "reviewed"
python3 tools/translate/run.py de                  # ~150 model calls, 10 s apart
#  read work/de/<run>/report/index.html
python3 tools/translate/run.py de --run <run> --promote
git add -A && git commit -m "Add the German edition"
```

## Retranslate with a new model

```bash
python3 tools/translate/run.py en --model claude-opus-6 --run opus6
#  work/en/opus6/report/index.html compares the published edition with the new run
python3 tools/translate/run.py en --model claude-opus-6 --run opus6 --promote   # if it is better
```

An earlier run can be compared with a new one directly:

```bash
python3 tools/report/report.py en --a run:opus6/final --b run:opus7/final --out work/en/cmp
```

## Change a glossary term

Edit the source in `glossary/terms.json` (add `"forms"` when automatic
inflection matching is not reliable) and its target in every
`glossary/targets.<code>.json`, then `python3 tools/glossary/build.py --all`.
`build.py` lists sources that never occur in the Russian text.

## Exit codes

Every check exits with 1 on an error, so it can gate CI or a script. The model
steps stop with a saved checkpoint on the subscription usage limit and continue
after the reset; rerunning the same `run.py` command resumes any step.
