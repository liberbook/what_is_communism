#!/usr/bin/env python3
"""Translate one edition end to end, with checks and a review report.

Steps (each one resumes where it stopped when the command is run again):
  glossary   build the edition's glossary (fails while targets are a draft)
  pass1      translation with TranslateBooksWithLLMs           -> <run>/draft
  check1     structure check of the draft
  pass2      bilingual review against the Russian source       -> <run>/reviewed
  check2     structure + glossary checks of the reviewed text
  final      typography and escaping, text only                -> <run>/final
  report     HTML report: published edition vs this run        -> <run>/report
  -- with --promote only --
  promote    write <run>/final into <dir>/parts
  build      ./build.sh <dir>
  verify     structure, glossary and build checks on the edition

Without --promote nothing outside work/ changes: read the report first, then
run the same command with --promote (the finished steps are skipped).

Usage:
  python3 tools/translate/run.py de [--model opus] [--delay 10] [--run NAME] [--promote]
  python3 tools/translate/run.py en --model claude-opus-6 --run opus6-test       # retranslate, compare
  python3 tools/translate/run.py en --model claude-opus-6 --run opus6-test --promote
"""
from __future__ import annotations

import argparse
import datetime
import json
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import edlib  # noqa: E402

TOOLS = edlib.ROOT / "tools"


def step(name: str, cmd: list[str], meta: dict, meta_path: Path, allow_fail: bool = False) -> bool:
    print(f"\n=== {name}: {' '.join(str(c) for c in cmd)}", flush=True)
    rc = subprocess.run([str(c) for c in cmd], cwd=edlib.ROOT).returncode
    meta["steps"][name] = {"exit": rc, "at": f"{datetime.datetime.now():%Y-%m-%d %H:%M:%S}"}
    meta_path.write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")
    if rc and not allow_fail:
        raise SystemExit(f"step {name} failed (exit {rc}); fix it and run the same command again")
    return rc == 0


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("code")
    ap.add_argument("--model", default="opus", help="Claude model alias or id (default: opus)")
    ap.add_argument("--delay", type=float, default=10.0, help="seconds between model calls (default: 10)")
    ap.add_argument("--run", help="run name (default: <model>-<date>); reuse it to resume")
    ap.add_argument("--skip-review", action="store_true", help="no pass 2: finalize the draft")
    ap.add_argument("--promote", action="store_true", help="write the run into the edition, build and verify")
    ap.add_argument("--parts", nargs="*", help="only these part numbers (for tests), e.g. 11")
    args = ap.parse_args()
    cfg = edlib.load_config()
    ed = cfg.edition(args.code)
    if not ed.translated:
        raise SystemExit(f"edition {ed.code} is not a pipeline translation (no target_language in languages.toml)")
    run = args.run or edlib.default_run_name(args.model)
    rd = edlib.run_dir(ed.code, run)
    rd.mkdir(parents=True, exist_ok=True)
    meta_path = rd / "run.json"
    meta = json.loads(meta_path.read_text(encoding="utf-8")) if meta_path.exists() else {
        "edition": ed.code, "run": run, "model": args.model, "delay": args.delay,
        "started": f"{datetime.datetime.now():%Y-%m-%d %H:%M:%S}", "steps": {}}
    py = sys.executable
    common = ["--model", args.model, "--run", run, "--delay", str(args.delay)]
    stage = "draft" if args.skip_review else "reviewed"
    sel = ["--parts", *args.parts] if args.parts else []

    step("glossary", [py, TOOLS / "glossary/build.py", ed.code], meta, meta_path)
    step("pass1", [py, TOOLS / "translate/pass1.py", ed.code, *common, *sel], meta, meta_path)
    step("check1", [py, TOOLS / "checks/structure.py", ed.code, "--dir", rd / "draft", "--no-typography", *sel], meta, meta_path)
    if not args.skip_review:
        step("pass2", [py, TOOLS / "translate/pass2.py", ed.code, *common, *sel], meta, meta_path)
        step("check2", [py, TOOLS / "checks/structure.py", ed.code, "--dir", rd / "reviewed", "--no-typography", *sel], meta, meta_path)
    step("final", [py, TOOLS / "translate/finalize.py", ed.code, "--run", run, "--from", stage, "--dry-run", *sel], meta, meta_path)
    step("check-final", [py, TOOLS / "checks/structure.py", ed.code, "--dir", rd / "final", *sel], meta, meta_path)
    step("glossary-final", [py, TOOLS / "checks/glossary.py", ed.code, "--dir", rd / "final", *sel], meta, meta_path, allow_fail=True)
    published = any(p.exists() for p in ed.part_paths())
    a = "edition" if published else f"run:{run}/draft"
    step("report", [py, TOOLS / "report/report.py", ed.code, "--a", a, "--b", f"run:{run}/final",
                    "--out", rd / "report"], meta, meta_path)
    if not args.promote:
        print(f"\nRun {edlib.rel(rd)} is ready. Read {edlib.rel(rd / 'report' / 'index.html')}"
              f" ({'published edition' if published else 'draft'} vs this run), then:\n"
              f"  python3 tools/translate/run.py {ed.code} --run {run} --model {args.model} --promote"
              + (f" --parts {' '.join(args.parts)}" if args.parts else ""))
        return
    step("promote", [py, TOOLS / "translate/finalize.py", ed.code, "--run", run, "--from", stage, *sel], meta, meta_path)
    step("build", ["./build.sh", ed.dir], meta, meta_path)
    ok = step("verify-structure", [py, TOOLS / "checks/structure.py", ed.code], meta, meta_path, allow_fail=True)
    ok &= step("verify-glossary", [py, TOOLS / "checks/glossary.py", ed.code], meta, meta_path, allow_fail=True)
    ok &= step("verify-build", [py, TOOLS / "checks/build.py", ed.code], meta, meta_path, allow_fail=True)
    step("docs", [py, TOOLS / "render_docs.py"], meta, meta_path)
    print(f"\n{'All checks passed' if ok else 'SOME CHECKS FAILED (see above)'}: {ed.dir}/parts and out/{ed.dir}/ updated; "
          f"review `git diff`, then commit.")
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
