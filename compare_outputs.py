#!/usr/bin/env python3
from __future__ import annotations

import html
import re
import subprocess
import sys
import tempfile
import zipfile
from html.parser import HTMLParser
from pathlib import Path

ROOT = Path(__file__).resolve().parent
EXPECTED = {
    "russian": ROOT.parent / "project" / "output" / "full",
    "italiano": ROOT.parent / "project_it" / "output" / "full",
}
GENERATED = {
    "russian": ROOT / "out" / "russian",
    "italiano": ROOT / "out" / "italiano",
}
FILENAMES = {
    "russian": "chto_takoe_kommunizm",
    "italiano": "che_cose_il_comunismo",
}


class TextExtractor(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.chunks: list[str] = []
        self.skip_depth = 0

    def handle_starttag(self, tag: str, attrs) -> None:
        if tag in {"style", "script"}:
            self.skip_depth += 1

    def handle_endtag(self, tag: str) -> None:
        if tag in {"style", "script"} and self.skip_depth:
            self.skip_depth -= 1

    def handle_data(self, data: str) -> None:
        if not self.skip_depth:
            self.chunks.append(data)

    def text(self) -> str:
        return " ".join(self.chunks)


def normalize(text: str) -> str:
    text = html.unescape(text)
    text = text.replace("\xa0", " ")
    text = text.replace("↩︎", " ")
    text = text.replace("↩", " ")
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def extract_pdf_text(path: Path) -> str:
    with tempfile.TemporaryDirectory() as tmp:
        txt = Path(tmp) / "out.txt"
        subprocess.run(["pdftotext", str(path), str(txt)], check=True, capture_output=True)
        return normalize(txt.read_text(encoding="utf-8", errors="ignore"))


def extract_markup_text(path: Path) -> str:
    raw = path.read_text(encoding="utf-8", errors="ignore")
    raw = re.sub(r"<binary\b[^>]*>.*?</binary>", "", raw, flags=re.DOTALL | re.IGNORECASE)
    parser = TextExtractor()
    parser.feed(raw)
    return normalize(parser.text())


def extract_epub_text(path: Path) -> str:
    parser = TextExtractor()
    with zipfile.ZipFile(path) as zf:
        names = sorted(
            n for n in zf.namelist()
            if n.endswith((".xhtml", ".html", ".htm"))
        )
        for name in names:
            parser.feed(zf.read(name).decode("utf-8", errors="ignore"))
    text = normalize(parser.text())
    text = re.sub(r"\b\d+ \. (?=[A-ZÀ-ÖØ-ÞА-ЯЁ])", "", text)
    return text


def extract_markdown_text(path: Path) -> str:
    result = subprocess.run(
        ["pandoc", str(path), "-f", "gfm+footnotes", "-t", "plain"],
        check=True,
        capture_output=True,
        text=True,
    )
    return normalize(result.stdout)


def compare_pair(label: str, expected: Path, generated: Path, extractor) -> tuple[bool, str]:
    a = extractor(expected)
    b = extractor(generated)
    if a == b:
        return True, f"OK   {label}"
    prefix = 0
    limit = min(len(a), len(b))
    while prefix < limit and a[prefix] == b[prefix]:
        prefix += 1
    a_snip = a[prefix:prefix + 200]
    b_snip = b[prefix:prefix + 200]
    return False, (
        f"DIFF {label}\n"
        f"  first mismatch at normalized char {prefix}\n"
        f"  expected: {a_snip!r}\n"
        f"  got     : {b_snip!r}"
    )


def main() -> int:
    all_ok = True
    plan = [
        ("screen pdf", "{base}.pdf", extract_pdf_text),
        ("print pdf", "print/{base}_print.pdf", extract_pdf_text),
        ("html", "{base}.html", extract_markup_text),
        ("fb2", "{base}.fb2", extract_markup_text),
        ("epub", "{base}.epub", extract_epub_text),
        ("markdown", "{base}.md", extract_markdown_text),
    ]
    for lang in ("russian", "italiano"):
        print(f"\n== {lang} ==")
        expected_base = EXPECTED[lang]
        generated_base = GENERATED[lang]
        base = FILENAMES[lang]
        for label, rel, extractor in plan:
            ok, message = compare_pair(
                label,
                expected_base / rel.format(base=base),
                generated_base / rel.format(base=base),
                extractor,
            )
            print(message)
            all_ok = all_ok and ok
    return 0 if all_ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
