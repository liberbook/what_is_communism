#!/usr/bin/env python3
"""Pass 1: translate every source part with TranslateBooksWithLLMs.

Runs TranslateBooksWithLLMs' translate.py on each exported source part
(work/source/*.txt) through the Claude Code CLI provider, with the edition's
glossary, and writes work/<code>/<run>/draft/. A part is skipped when its
".done" marker exists, so rerunning the same command resumes. When the
subscription usage limit stops a part, the job is resumed from its checkpoint
after the reset time printed by the CLI (or 30 minutes).

Usage: python3 tools/translate/pass1.py en [--run NAME] [--model opus] [--delay 10] [--parts 03 07]
"""
from __future__ import annotations

import argparse
import datetime
import os
import re
import subprocess
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import edlib  # noqa: E402


def wait_for_reset(log_text: str) -> None:
    m = re.findall(r"[Rr]esets at ([^.\n]+)", log_text)
    if m and m[-1].strip() != "None":
        try:
            target = subprocess.run(["date", "-d", m[-1].strip(), "+%s"], capture_output=True, text=True, check=True)
            wait = int(target.stdout) - int(time.time())
            if wait > 0:
                print(f"[pass1] usage limit: sleeping until {m[-1].strip()} (+90 s)", flush=True)
                time.sleep(wait + 90)
                return
        except (subprocess.CalledProcessError, ValueError):
            pass
    print("[pass1] usage limit: reset time unknown, sleeping 30 min", flush=True)
    time.sleep(1800)


def translate_part(ed: edlib.Edition, src: Path, out: Path, log: Path, args: argparse.Namespace) -> bool:
    env = dict(os.environ, CLAUDE_CLI_DELAY_SECONDS=str(args.delay), MAX_TOKENS_PER_CHUNK=str(args.chunk_tokens),
               ATTRIBUTION_ENABLED="false", MAX_TRANSLATION_ATTEMPTS="3", REQUEST_TIMEOUT="600")
    python = edlib.TBL_ROOT / "venv" / "bin" / "python"
    resume: list[str] = []
    for attempt in range(1, 6):
        if not resume and out.exists():
            out.unlink()  # a stale partial file would make translate.py pick another name
        cmd = [str(python if python.exists() else sys.executable), str(edlib.TBL_ROOT / "translate.py"),
               "-i", str(src), "-o", str(out), "-sl", edlib.load_config().source.english_name,
               "-tl", ed.target_language, "--provider", "claude-cli", "-m", args.model,
               "--glossary", str(ed.glossary_path), "--no-color", *resume]
        print(f"[pass1] {datetime.datetime.now():%H:%M:%S} {src.name} (attempt {attempt})", flush=True)
        with log.open("a", encoding="utf-8") as lf:
            proc = subprocess.run(cmd, cwd=edlib.TBL_ROOT, env=env, stdout=lf, stderr=subprocess.STDOUT,
                                  stdin=subprocess.DEVNULL)
        text = log.read_text(encoding="utf-8", errors="replace")
        if proc.returncode == 0 and out.exists() and out.stat().st_size:
            return True
        ids = re.findall(r"--resume (cli_[0-9a-f]+)", text)
        if ids:
            resume = ["--resume", ids[-1]]
            wait_for_reset(text)
            continue
        print(f"[pass1] {src.name} failed (exit {proc.returncode}), see {edlib.rel(log)}; retrying in 120 s", flush=True)
        time.sleep(120)
    return False


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("code")
    ap.add_argument("--model", default="opus", help="Claude model alias or id (default: opus)")
    ap.add_argument("--run", help="run name (default: <model>-<date>)")
    ap.add_argument("--delay", type=float, default=10.0, help="seconds between model calls (default: 10)")
    ap.add_argument("--chunk-tokens", type=int, default=1500)
    ap.add_argument("--parts", nargs="*", help="part numbers to translate (default: all), e.g. 03 07")
    args = ap.parse_args()
    cfg = edlib.load_config()
    ed = cfg.edition(args.code)
    if not ed.translated:
        raise SystemExit(f"edition {ed.code} is not a pipeline translation (no target_language)")
    if not ed.glossary_path or not ed.glossary_path.exists():
        raise SystemExit(f"glossary {ed.get('glossary')} missing: run python3 tools/glossary/build.py {ed.code}")
    run = args.run or edlib.default_run_name(args.model)
    rd = edlib.run_dir(ed.code, run)
    (rd / "draft").mkdir(parents=True, exist_ok=True)
    (rd / "logs").mkdir(exist_ok=True)
    sources = edlib.export_source(cfg)
    failed = []
    for src in sources:
        if args.parts and src.name[:2] not in args.parts:
            continue
        out = rd / "draft" / src.name
        if Path(f"{out}.done").exists():
            print(f"[pass1] skip {src.name} (done)")
            continue
        if translate_part(ed, src, out, rd / "logs" / f"pass1_{src.stem}.log", args):
            Path(f"{out}.done").touch()
        else:
            failed.append(src.name)
    print(f"[pass1] run {edlib.rel(rd)}: {'all parts done' if not failed else 'FAILED: ' + ', '.join(failed)}")
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()
