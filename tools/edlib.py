"""Shared helpers for the edition tools: config, paths and LaTeX part I/O.

Every tool in tools/ imports this module (it adds itself to sys.path through
the small bootstrap at the top of each script). Nothing here needs anything
outside the Python standard library.
"""
from __future__ import annotations

import os
import re
import sys
import tomllib
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
CONFIG = ROOT / "languages.toml"
WORK = ROOT / "work"                     # gitignored: exports, runs, reports
TBL_ROOT = Path(os.environ.get("TBL_ROOT", Path.home() / "work" / "TranslateBooksWithLLMs"))

sys.path.insert(0, str(ROOT))
from parts_text_exchange import parse_latex_part  # noqa: E402  (repo-root module)


@dataclass
class Edition:
    data: dict[str, Any]

    def __getattr__(self, key: str) -> Any:
        try:
            return self.data[key]
        except KeyError as e:
            raise AttributeError(key) from e

    def get(self, key: str, default: Any = None) -> Any:
        return self.data.get(key, default)

    @property
    def src(self) -> Path:
        return ROOT / self.dir

    @property
    def parts_dir(self) -> Path:
        return self.src / "parts"

    @property
    def is_source(self) -> bool:
        return bool(self.data.get("source"))

    @property
    def translated(self) -> bool:
        """Produced by the tools/translate pipeline (has a target language)."""
        return "target_language" in self.data

    def part_paths(self) -> list[Path]:
        return [self.parts_dir / f"{slug}.tex" for slug in self.parts]

    @property
    def glossary_path(self) -> Path | None:
        g = self.data.get("glossary")
        return ROOT / g if g else None


@dataclass
class Config:
    data: dict[str, Any]
    editions: list[Edition] = field(default_factory=list)

    @property
    def source(self) -> Edition:
        return next(e for e in self.editions if e.is_source)

    def edition(self, key: str) -> Edition:
        for e in self.editions:
            if key in (e.code, e.dir):
                return e
        raise SystemExit(f"unknown edition {key!r}; known: {', '.join(e.code for e in self.editions)}")


def load_config(path: Path = CONFIG) -> Config:
    data = tomllib.loads(path.read_text(encoding="utf-8"))
    eds = [Edition(e) for e in data.get("edition", [])]
    if sum(e.is_source for e in eds) != 1:
        raise SystemExit("languages.toml: exactly one edition must have source = true")
    for e in eds:
        if len(e.parts) != len(eds[0].parts):
            raise SystemExit(f"languages.toml: edition {e.code} has {len(e.parts)} parts, expected {len(eds[0].parts)}")
    return Config(data, eds)


# --- parts --------------------------------------------------------------------

@dataclass
class Part:
    """One LaTeX part as text: title, body paragraphs ([[FNn]] markers) and footnotes."""
    path: Path
    page: int
    title: str
    label: str
    paragraphs: list[str]
    footnotes: list[str]


def read_part(path: Path) -> Part:
    p = parse_latex_part(path)
    return Part(path, p.page, p.title, p.label, p.paragraphs, p.footnotes)


def read_text_blocks(path: Path) -> list[str]:
    """Blank-line separated blocks of a simple-format text part."""
    return [b.strip() for b in re.split(r"\n\s*\n", path.read_text(encoding="utf-8").strip()) if b.strip()]


def part_as_blocks(part: Part) -> list[str]:
    """The simple text format of parts_text_exchange: title, paragraphs, [n] notes."""
    body = [re.sub(r"\[\[FN(\d+)\]\]", r"[\1]", p) for p in part.paragraphs]
    notes = [f"[{i}] {n.strip()}" for i, n in enumerate(part.footnotes, start=1)]
    return [part.title, *body, *notes]


def edition_blocks(ed: Edition) -> list[list[str]]:
    """Every part of an edition as simple-format blocks (empty list for a missing part)."""
    out = []
    for path in ed.part_paths():
        out.append(part_as_blocks(read_part(path)) if path.exists() else [])
    return out


def latex_text(s: str) -> str:
    """Escape a short plain string (title, author) for LaTeX."""
    s = s.replace("\\", r"\textbackslash{}")
    return re.sub(r"([%&#$_{}])", r"\\\1", s)


def rel(path: Path) -> str:
    """Path relative to the repository root when possible, for messages."""
    try:
        return str(Path(path).resolve().relative_to(ROOT))
    except ValueError:
        return str(path)


def use_tbl() -> None:
    """Make TranslateBooksWithLLMs importable, re-running under its venv if needed.

    The translation tools reuse TranslateBooksWithLLMs (its Claude Code CLI
    provider, chunker and glossary filter). Set TBL_ROOT if it is not in
    ~/work/TranslateBooksWithLLMs.
    """
    if not (TBL_ROOT / "translate.py").exists():
        raise SystemExit(f"TranslateBooksWithLLMs not found in {TBL_ROOT}; set TBL_ROOT")
    venv_python = TBL_ROOT / "venv" / "bin" / "python"
    if venv_python.exists() and Path(sys.prefix).resolve() != (TBL_ROOT / "venv").resolve() \
            and not os.environ.get("EDLIB_NO_REEXEC"):
        os.environ["EDLIB_NO_REEXEC"] = "1"
        os.execv(str(venv_python), [str(venv_python), *sys.argv])
    sys.path.insert(0, str(TBL_ROOT))


# --- translation runs -----------------------------------------------------------

SOURCE_TXT = WORK / "source"


def source_txt_paths(cfg: Config | None = None) -> list[Path]:
    """Exported source parts (simple text format), one per part, in book order."""
    cfg = cfg or load_config()
    out = []
    for path in cfg.source.part_paths():
        part = read_part(path)
        out.append(SOURCE_TXT / f"{path.stem}__p{part.page:03d}.txt")
    return out


def export_source(cfg: Config | None = None) -> list[Path]:
    """Write the source parts as simple text into work/source/ (idempotent)."""
    cfg = cfg or load_config()
    SOURCE_TXT.mkdir(parents=True, exist_ok=True)
    paths = source_txt_paths(cfg)
    for tex, txt in zip(cfg.source.part_paths(), paths):
        text = "\n\n".join(part_as_blocks(read_part(tex))) + "\n"
        if not txt.exists() or txt.read_text(encoding="utf-8") != text:
            txt.write_text(text, encoding="utf-8")
    return paths


def run_dir(code: str, run: str) -> Path:
    return WORK / code / run


def default_run_name(model: str) -> str:
    import datetime
    return f"{model.replace('/', '_')}-{datetime.date.today():%Y%m%d}"
