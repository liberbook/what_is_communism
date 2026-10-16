# What is communism? / Что такое коммунизм? / Che cos'è il comunismo?

[![Read online](https://img.shields.io/badge/read-online-b0301e)](https://liberbook.github.io/what_is_communism/)
[![Release](https://img.shields.io/github/v/release/liberbook/what_is_communism?label=release)](https://github.com/liberbook/what_is_communism/releases/latest)
[![Downloads](https://img.shields.io/github/downloads/liberbook/what_is_communism/total?label=downloads)](https://github.com/liberbook/what_is_communism/releases)
[![Build](https://github.com/liberbook/what_is_communism/actions/workflows/build.yml/badge.svg)](https://github.com/liberbook/what_is_communism/actions/workflows/build.yml)
![Languages](https://img.shields.io/badge/languages-ru%20%C2%B7%20uk%20%C2%B7%20it-c0392b)
![Formats](https://img.shields.io/badge/formats-PDF%20%C2%B7%20EPUB%20%C2%B7%20FB2-555)
![Made with LaTeX](https://img.shields.io/badge/made%20with-LaTeX-008080?logo=latex&logoColor=white)

## Читать онлайн · Читати онлайн · Leggi online

[Русский](https://liberbook.github.io/what_is_communism/ru/) · [Українська](https://liberbook.github.io/what_is_communism/uk/) · [Italiano](https://liberbook.github.io/what_is_communism/it/) — или главная страница: [liberbook.github.io/what_is_communism/](https://liberbook.github.io/what_is_communism/)

## Скачать · Завантажити · Scarica

| | Читать с экрана (A4) | Печать (A5) | Брошюра на A4 (двусторонняя печать) | EPUB | FB2 |
|---|---|---|---|---|---|
| **Русский** — Что такое коммунизм? | [PDF](https://github.com/liberbook/what_is_communism/releases/latest/download/chto_takoe_kommunizm.pdf) | [PDF](https://github.com/liberbook/what_is_communism/releases/latest/download/chto_takoe_kommunizm_print.pdf) | [PDF](https://github.com/liberbook/what_is_communism/releases/latest/download/chto_takoe_kommunizm_booklet_a4.pdf) | [EPUB](https://github.com/liberbook/what_is_communism/releases/latest/download/chto_takoe_kommunizm.epub) | [FB2](https://github.com/liberbook/what_is_communism/releases/latest/download/chto_takoe_kommunizm.fb2) |
| **Українська** — Що таке комунізм? | [PDF](https://github.com/liberbook/what_is_communism/releases/latest/download/shcho_take_komunizm.pdf) | [PDF](https://github.com/liberbook/what_is_communism/releases/latest/download/shcho_take_komunizm_print.pdf) | [PDF](https://github.com/liberbook/what_is_communism/releases/latest/download/shcho_take_komunizm_booklet_a4.pdf) | [EPUB](https://github.com/liberbook/what_is_communism/releases/latest/download/shcho_take_komunizm.epub) | [FB2](https://github.com/liberbook/what_is_communism/releases/latest/download/shcho_take_komunizm.fb2) |
| **Italiano** — Che cos'è il comunismo? | [PDF](https://github.com/liberbook/what_is_communism/releases/latest/download/che_cose_il_comunismo.pdf) | [PDF](https://github.com/liberbook/what_is_communism/releases/latest/download/che_cose_il_comunismo_print.pdf) | [PDF](https://github.com/liberbook/what_is_communism/releases/latest/download/che_cose_il_comunismo_booklet_a4.pdf) | [EPUB](https://github.com/liberbook/what_is_communism/releases/latest/download/che_cose_il_comunismo.epub) | [FB2](https://github.com/liberbook/what_is_communism/releases/latest/download/che_cose_il_comunismo.fb2) |

Все версии — в [релизах](https://github.com/liberbook/what_is_communism/releases). Every version: [Releases](https://github.com/liberbook/what_is_communism/releases).

## About · О проекте

See [GOAL.md](GOAL.md) for the project's goals and the recommended AI-driven translation workflow — it explains the conversion, verification, and translation steps used throughout this repository.
The same files are also in [`results/`](results/) (Markdown and HTML versions too, readable right on GitHub: [RU](results/russian/chto_takoe_kommunizm.md) · [UK](results/ukrainian/shcho_take_komunizm.md) · [IT](results/italiano/che_cose_il_comunismo.md)).

This repository contains three compact LaTeX editions of the same political-theoretical booklet:

- `russian/` — Russian edition (the original, by «Группа Энгельс»): **Что такое коммунизм?**
- `ukrainian/` — Ukrainian edition: **Що таке комунізм?**
- `italiano/` — Italian edition: **Che cos'è il comunismo?**

The Italian edition is a translation from Russian made with Claude Opus 5.5 (`claude-opus-5-5`) through [TranslateBooksWithLLMs](https://github.com/hydropix/TranslateBooksWithLLMs): a glossary-driven translation pass followed by a bilingual review pass against the Russian source.

### По-русски

Этот текст объясняет коммунизм не как миф, ругательство или ностальгический символ, а как серьёзную теорию понимания и преобразования общества. В начале брошюры подчёркивается, что само слово «коммунизм» было исторически искажено, что о нём часто спорят без понимания его научного смысла, и что коммунистическую теорию нужно вернуть как практическую оптику для анализа современного общества, эксплуатации и освобождения.

### In italiano

Questo testo presenta il comunismo non come mito, insulto o slogan nostalgico, ma come una teoria seria per comprendere e trasformare la società. Nelle prime pagine insiste su tre idee: il termine «comunismo» è stato storicamente deformato, molti ne parlano senza conoscerne il significato scientifico, e la teoria comunista deve essere recuperata come strumento pratico per leggere di nuovo la società contemporanea, lo sfruttamento e l’emancipazione.

La versione italiana inclusa in questo repository è stata tradotta dal russo con Claude Opus 5.5 tramite TranslateBooksWithLLMs: una traduzione guidata da un glossario, seguita da una revisione bilingue sul testo russo.

## Repository layout

```text
russian/    # self-contained LaTeX source for the Russian edition
ukrainian/  # self-contained LaTeX source for the Ukrainian edition
italiano/   # self-contained LaTeX source for the Italian edition
build.sh    # builds PDF + print PDF + EPUB + FB2 + HTML + Markdown
Dockerfile  # minimal containerized build environment
```

## Required software for local build

- `python3`
- `pdflatex`
- `pandoc`
- `poppler-utils` (only if you want to run the comparison script)

On Debian/Ubuntu-like systems, the LaTeX packages normally come from:

- `texlive-latex-base`
- `texlive-latex-recommended`
- `texlive-latex-extra`
- `texlive-fonts-recommended`
- `texlive-lang-cyrillic`

## Build locally

Build everything:

```sh
./build.sh
```

Build one edition only:

```sh
./build.sh russian
./build.sh ukrainian
./build.sh italiano
```

Generated files are written to `out/russian/`, `out/ukrainian/`, and `out/italiano/`.

Each edition produces:

- `chto_takoe_kommunizm.pdf` / `che_cose_il_comunismo.pdf` — screen PDF (A4)
- `print/chto_takoe_kommunizm_print.pdf` / `print/che_cose_il_comunismo_print.pdf` — print PDF (A5)
- `print/chto_takoe_kommunizm_booklet_a4.pdf` / `print/che_cose_il_comunismo_booklet_a4.pdf` — booklet-imposed PDF for duplex printing on A4
- `chto_takoe_kommunizm.epub` / `che_cose_il_comunismo.epub`
- `chto_takoe_kommunizm.fb2` / `che_cose_il_comunismo.fb2`
- `chto_takoe_kommunizm.html` / `che_cose_il_comunismo.html`
- `chto_takoe_kommunizm.md` / `che_cose_il_comunismo.md`
- `chto_takoe_kommunizm_flat.tex` / `che_cose_il_comunismo_flat.tex`

## Build with Docker

```sh
./docker_build.sh
```

This builds a small Debian-based image with the exact toolchain needed for the project, then runs the same `build.sh` script inside the container. GitHub Actions runs the same build on every push (`.github/workflows/build.yml`): the files it produces are kept for 30 days as the run's artifact, and the HTML editions with the landing page `site/index.html` are published to GitHub Pages.

## Compare results with the original workspace outputs

After building locally, you can verify that the generated texts match the already produced outputs from the working project:

```sh
python3 compare_outputs.py
```

The comparison is text-based:

- PDFs are compared through `pdftotext`
- EPUB is compared by extracting text from its internal XHTML files
- HTML and FB2 are compared after stripping markup and normalizing whitespace
- Markdown is compared by converting it to plain text with `pandoc`

## Note on the Italian edition

The Italian preamble intentionally uses English babel support, because this keeps the dependency set small and matches the current working edition. This does **not** change the text itself; it only affects automatic hyphenation patterns.
