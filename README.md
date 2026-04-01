# What is communism? / Che cos'è il comunismo?

See [GOAL.md](GOAL.md) for the project's goals and the recommended AI-driven translation workflow — it explains the conversion, verification, and translation steps used throughout this repository.

See the `results/` directory for full build artifacts and print versions.

- **Russian**: [PDF](results/russian/pdf/chto_takoe_kommunizm.pdf), [EPUB](results/russian/chto_takoe_kommunizm.epub), [FB2](results/russian/chto_takoe_kommunizm.fb2), [MD](results/russian/chto_takoe_kommunizm.md)
 - **Ukrainian**: [PDF](results/ukrainian/pdf/shcho_take_komunizm.pdf), [EPUB](results/ukrainian/shcho_take_komunizm.epub), [FB2](results/ukrainian/shcho_take_komunizm.fb2), [MD](results/ukrainian/shcho_take_komunizm.md)
 - **Italiano**: [PDF](results/italiano/pdf/che_cose_il_comunismo.pdf), [EPUB](results/italiano/che_cose_il_comunismo.epub), [FB2](results/italiano/che_cose_il_comunismo.fb2), [MD](results/italiano/che_cose_il_comunismo.md)

This repository contains three compact LaTeX editions of the same political-theoretical booklet:

- `russian/` — Russian edition: **Что такое коммунизм?**
- `ukrainian/` — Ukrainian edition: **Що таке комунізм?**
- `italiano/` — Italian edition: **Che cos'è il comunismo?**

The Italian edition is a translation from Russian made with `translategemma:27b`.

### По-русски

Этот текст объясняет коммунизм не как миф, ругательство или ностальгический символ, а как серьёзную теорию понимания и преобразования общества. В начале брошюры подчёркивается, что само слово «коммунизм» было исторически искажено, что о нём часто спорят без понимания его научного смысла, и что коммунистическую теорию нужно вернуть как практическую оптику для анализа современного общества, эксплуатации и освобождения.

### In italiano

Questo testo presenta il comunismo non come mito, insulto o slogan nostalgico, ma come una teoria seria per comprendere e trasformare la società. Nelle prime pagine insiste su tre idee: il termine «comunismo» è stato storicamente deformato, molti ne parlano senza conoscerne il significato scientifico, e la teoria comunista deve essere recuperata come strumento pratico per leggere di nuovo la società contemporanea, lo sfruttamento e l’emancipazione.

La versione italiana inclusa in questo repository è stata tradotta dal russo con `translategemma:27b`.

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

This builds a small Debian-based image with the exact toolchain needed for the project, then runs the same `build.sh` script inside the container.

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
