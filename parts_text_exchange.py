#!/usr/bin/env python3
from __future__ import annotations

import argparse
import re
from dataclasses import dataclass
from pathlib import Path

PART_TEMPLATE = """\\documentclass[../main]{{subfiles}}
\\begin{{document}}
\\ifSubfilesClassLoaded{{\\setcounter{{page}}{{{page}}}}}{{}}
\\section{{{title}}}
\\label{{{label}}}

{body}
\\end{{document}}
"""

VERBOSE_TEMPLATE = """=== META ===
slug: {slug}
page: {page}
title: {title}
label: {label}

=== BODY ===
{body_blocks}
=== FOOTNOTES ===
{footnote_blocks}
"""


@dataclass
class PartData:
    slug: str
    page: int
    title: str
    label: str
    paragraphs: list[str]
    footnotes: list[str]


def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def write_text(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def split_footnotes(text: str, marker_template: str) -> tuple[str, list[str]]:
    notes: list[str] = []
    out: list[str] = []
    i = 0
    while i < len(text):
        if text.startswith(r"\footnote{", i):
            j = i + len(r"\footnote{")
            depth = 1
            buf: list[str] = []
            while j < len(text) and depth > 0:
                ch = text[j]
                if ch == "{" and text[j - 1] != "\\":
                    depth += 1
                    buf.append(ch)
                elif ch == "}" and text[j - 1] != "\\":
                    depth -= 1
                    if depth > 0:
                        buf.append(ch)
                else:
                    buf.append(ch)
                j += 1
            notes.append("".join(buf))
            out.append(marker_template.format(n=len(notes)))
            i = j
        else:
            out.append(text[i])
            i += 1
    return "".join(out), notes


def merge_footnotes(text: str, notes: list[str], pattern: str) -> str:
    def repl(match: re.Match[str]) -> str:
        idx = int(match.group(1)) - 1
        if idx < 0 or idx >= len(notes):
            return match.group(0)
        return r"\footnote{" + notes[idx] + "}"

    return re.sub(pattern, repl, text)


def parse_latex_part(path: Path) -> PartData:
    text = read_text(path)
    page_m = re.search(r"\\ifSubfilesClassLoaded\{\\setcounter\{page\}\{(\d+)\}\}\{\}", text)
    title_m = re.search(r"\\section\{(.*?)\}", text, re.DOTALL)
    label_m = re.search(r"\\label\{(.*?)\}", text)
    body_m = re.search(r"\\label\{.*?\}\s*(.*?)\s*\\end\{document\}", text, re.DOTALL)
    if not (page_m and title_m and label_m and body_m):
        raise ValueError(f"Could not parse LaTeX part: {path}")

    body = body_m.group(1).strip()
    paragraphs = [p.strip() for p in re.split(r"\n\s*\n", body) if p.strip()]
    all_notes: list[str] = []
    normalized_paras: list[str] = []
    for para in paragraphs:
        normalized, notes = split_footnotes(para, "[[FN{n}]]")
        offset = len(all_notes)
        if notes:
            for idx in range(len(notes), 0, -1):
                normalized = normalized.replace(f"[[FN{idx}]]", f"[[FN{offset + idx}]]")
            all_notes.extend(notes)
        normalized_paras.append(normalized)

    return PartData(
        slug=path.stem,
        page=int(page_m.group(1)),
        title=title_m.group(1).strip(),
        label=label_m.group(1).strip(),
        paragraphs=normalized_paras,
        footnotes=all_notes,
    )


def filename_for_simple_export(part: PartData) -> str:
    return f"{part.slug}__p{part.page:03d}.txt"


def render_simple_text_part(part: PartData) -> str:
    paragraphs = []
    for para in part.paragraphs:
        converted = re.sub(r"\[\[FN(\d+)\]\]", r"[\1]", para)
        paragraphs.append(converted.strip())

    chunks = [part.title.strip(), *paragraphs]
    if part.footnotes:
        for idx, note in enumerate(part.footnotes, start=1):
            chunks.append(f"[{idx}] {note.strip()}")
    return "\n\n".join(chunks).rstrip() + "\n"


def render_verbose_text_part(part: PartData) -> str:
    body_blocks = []
    for idx, para in enumerate(part.paragraphs, start=1):
        body_blocks.append(f"[[P{idx}]]\n{para.strip()}\n")
    footnote_blocks = []
    for idx, note in enumerate(part.footnotes, start=1):
        footnote_blocks.append(f"[[FN{idx}]]\n{note.strip()}\n")
    return VERBOSE_TEMPLATE.format(
        slug=part.slug,
        page=part.page,
        title=part.title,
        label=part.label,
        body_blocks="\n".join(body_blocks),
        footnote_blocks="\n".join(footnote_blocks),
    )


def parse_filename_metadata(path: Path) -> tuple[str, int, str]:
    stem = path.stem
    match = re.match(r"(?P<slug>.+?)__p(?P<page>\d+)(?:__.*)?$", stem)
    if not match:
        raise ValueError(
            "Simple import expects filenames like '01_slug__p004.txt' or '01_slug__p004__uk.txt'"
        )
    slug = match.group("slug")
    page = int(match.group("page"))
    label = f"sec:{slug}"
    return slug, page, label


def read_reference_paragraph_lengths(path: Path) -> list[int] | None:
    candidate = path.parent.parent / "parts" / path.name
    if not candidate.exists() or candidate.resolve() == path.resolve():
        return None
    text = read_text(candidate).strip()
    if not text:
        return None
    blocks = [b.strip() for b in re.split(r"\n\s*\n", text) if b.strip()]
    if not blocks:
        return None
    body_blocks = blocks[1:]
    while body_blocks and re.match(r"^\[(\d+)\]\s+", body_blocks[-1], re.DOTALL):
        body_blocks.pop()
    if body_blocks:
        return [len(block) for block in body_blocks]
    return None


def partition_lines_by_reference(lines: list[str], target_lengths: list[int]) -> list[str]:
    if len(lines) < len(target_lengths):
        return lines
    prefix = [0]
    for line in lines:
        prefix.append(prefix[-1] + len(line))

    total_actual = prefix[-1]
    total_target = sum(target_lengths)
    scale = (total_actual / total_target) if total_target else 1.0
    n = len(lines)
    m = len(target_lengths)
    inf = float("inf")
    dp = [[inf] * (m + 1) for _ in range(n + 1)]
    prev = [[-1] * (m + 1) for _ in range(n + 1)]
    dp[0][0] = 0.0

    for i in range(1, n + 1):
        upper = min(i, m)
        for j in range(1, upper + 1):
            k_min = j - 1
            k_max = i - 1
            target = target_lengths[j - 1] * scale
            for k in range(k_min, k_max + 1):
                if dp[k][j - 1] == inf:
                    continue
                length = prefix[i] - prefix[k]
                score = (length - target) ** 2
                candidate = dp[k][j - 1] + score
                if candidate < dp[i][j]:
                    dp[i][j] = candidate
                    prev[i][j] = k

    if dp[n][m] == inf:
        return lines

    groups: list[str] = []
    i = n
    j = m
    while j > 0:
        k = prev[i][j]
        if k < 0:
            return lines
        groups.append(" ".join(line.strip() for line in lines[k:i]))
        i = k
        j -= 1
    groups.reverse()
    return groups


def sentence_segments(lines: list[str]) -> list[str]:
    segments: list[str] = []
    for line in lines:
        parts = re.split(r'(?<=[.!?…»”])\s+(?=[A-ZА-ЯЁІЇЄҐ«"\(])', line.strip())
        segments.extend(part.strip() for part in parts if part.strip())
    return segments


def split_simple_blocks(raw_text: str, target_lengths: list[int] | None) -> tuple[str, list[str], list[str]]:
    stripped = raw_text.strip()
    if not stripped:
        raise ValueError("Empty text part")

    lines = [line.rstrip() for line in stripped.splitlines()]
    nonempty_lines = [line.strip() for line in lines if line.strip()]
    if not nonempty_lines:
        raise ValueError("Empty text part")

    title = nonempty_lines[0]
    blocks = [b.strip() for b in re.split(r"\n\s*\n", stripped) if b.strip()]
    body_blocks = blocks[1:] if blocks else []
    footnote_blocks: list[str] = []
    while body_blocks and re.match(r"^\[(\d+)\]\s+", body_blocks[-1], re.DOTALL):
        footnote_blocks.append(body_blocks.pop())
    footnote_blocks.reverse()

    body_lines = [line.strip() for line in nonempty_lines[1:]]
    while body_lines and re.match(r"^\[(\d+)\]\s+", body_lines[-1], re.DOTALL):
        if not footnote_blocks:
            footnote_blocks.insert(0, body_lines[-1])
        body_lines.pop()

    if target_lengths is not None:
        if len(body_blocks) == len(target_lengths):
            return title, body_blocks, footnote_blocks
        segmented_lines = sentence_segments(body_lines)
        if len(segmented_lines) >= len(target_lengths):
            return title, partition_lines_by_reference(segmented_lines, target_lengths), footnote_blocks
        if len(body_lines) >= len(target_lengths):
            return title, partition_lines_by_reference(body_lines, target_lengths), footnote_blocks

    if body_blocks and len(body_blocks) >= max(2, len(body_lines) // 2):
        return title, body_blocks, footnote_blocks
    return title, body_lines, footnote_blocks


def parse_simple_text_part(path: Path) -> PartData:
    slug, page, label = parse_filename_metadata(path)
    raw_text = read_text(path)
    target_lengths = read_reference_paragraph_lengths(path)
    title, body_blocks, footnote_blocks = split_simple_blocks(raw_text, target_lengths)
    footnotes: list[str] = []
    for idx, block in enumerate(footnote_blocks, start=1):
        match = re.match(r"^\[(\d+)\]\s+(.*)$", block, re.DOTALL)
        if not match:
            raise ValueError(f"Invalid footnote block in {path}: {block[:40]!r}")
        number = int(match.group(1))
        if number != idx:
            raise ValueError(f"Footnotes in {path} must be consecutive starting from [1]")
        footnotes.append(match.group(2).strip())

    paragraphs = body_blocks
    return PartData(
        slug=slug,
        page=page,
        title=title,
        label=label,
        paragraphs=paragraphs,
        footnotes=footnotes,
    )


def parse_verbose_text_part(path: Path) -> PartData:
    text = read_text(path)
    headings = list(re.finditer(r"^===.*?===\s*$", text, re.MULTILINE))
    if len(headings) < 3:
        raise ValueError(f"Could not parse verbose text part: {path}")

    meta_text = text[headings[0].end():headings[1].start()].strip()
    body_text = text[headings[1].end():headings[2].start()].strip()
    notes_text = text[headings[2].end():].strip()

    meta: dict[str, str] = {}
    for line in meta_text.splitlines():
        line = line.strip()
        if not line or ":" not in line:
            continue
        key, value = line.split(":", 1)
        meta[key.strip()] = value.strip()

    body_chunks = re.findall(r"\[\[P\d+\]\]\n(.*?)(?=\n\[\[P\d+\]\]\n|\Z)", body_text, re.DOTALL)
    note_chunks = re.findall(r"\[\[FN\d+\]\]\n(.*?)(?=\n\[\[FN\d+\]\]\n|\Z)", notes_text, re.DOTALL)

    return PartData(
        slug=meta["slug"],
        page=int(meta["page"]),
        title=meta["title"],
        label=meta.get("label", f"sec:{meta['slug']}"),
        paragraphs=[chunk.strip() for chunk in body_chunks if chunk.strip()],
        footnotes=[chunk.strip() for chunk in note_chunks if chunk.strip()],
    )


def parse_text_part(path: Path) -> PartData:
    text = read_text(path)
    if re.search(r"^===.*?===\s*$", text, re.MULTILINE):
        return parse_verbose_text_part(path)
    return parse_simple_text_part(path)


def render_latex_part(part: PartData) -> str:
    paragraphs = []
    for para in part.paragraphs:
        para = merge_footnotes(para, part.footnotes, r"\[\[FN(\d+)\]\]")
        para = merge_footnotes(para, part.footnotes, r"\[(\d+)\]")
        paragraphs.append(para)
    body = "\n\n".join(paragraphs)
    return PART_TEMPLATE.format(
        page=part.page,
        title=part.title,
        label=part.label,
        body=body,
    )


def export_parts(input_dir: Path, output_dir: Path, format_name: str) -> None:
    files = sorted(input_dir.glob("*.tex"))
    if not files:
        raise SystemExit(f"No .tex files found in {input_dir}")
    for path in files:
        part = parse_latex_part(path)
        if format_name == "simple":
            out_path = output_dir / filename_for_simple_export(part)
            write_text(out_path, render_simple_text_part(part))
        else:
            out_path = output_dir / f"{part.slug}.txt"
            write_text(out_path, render_verbose_text_part(part))
        print(f"EXPORT {path.name} -> {out_path.name}")


def import_parts(input_dir: Path, output_dir: Path) -> None:
    files = sorted(input_dir.glob("*.txt"))
    if not files:
        raise SystemExit(f"No .txt files found in {input_dir}")
    for path in files:
        part = parse_text_part(path)
        out_path = output_dir / f"{part.slug}.tex"
        write_text(out_path, render_latex_part(part))
        print(f"IMPORT {path.name} -> {out_path.name}")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Export LaTeX part files to reversible text files and import them back."
    )
    sub = parser.add_subparsers(dest="command", required=True)

    export_parser = sub.add_parser("export", help="Convert .tex part files to text files")
    export_parser.add_argument("input_dir", type=Path)
    export_parser.add_argument("output_dir", type=Path)
    export_parser.add_argument(
        "--format",
        choices=("simple", "verbose"),
        default="simple",
        help="simple = translation-friendly minimal format (default), verbose = old explicit tagged format",
    )

    import_parser = sub.add_parser("import", help="Convert text files back to .tex part files")
    import_parser.add_argument("input_dir", type=Path)
    import_parser.add_argument("output_dir", type=Path)

    args = parser.parse_args()
    if args.command == "export":
        export_parts(args.input_dir, args.output_dir, args.format)
    else:
        import_parts(args.input_dir, args.output_dir)


if __name__ == "__main__":
    main()
