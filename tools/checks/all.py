#!/usr/bin/env python3
"""Run every AI-free check; exit code 1 if any fails. Used by CI after the build.

  tools/render_docs.py --check   site/index.html and README.md match languages.toml
  tools/checks/structure.py      translated parts against the source
  tools/checks/glossary.py       glossary targets used in the translations
  tools/checks/build.py          outputs of build_book.py (skipped with --no-build)

Usage: python3 tools/checks/all.py [--no-build]
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

TOOLS = Path(__file__).resolve().parent.parent


def main() -> None:
    steps = [["render_docs.py", "--check"], ["checks/structure.py", "-q"], ["checks/glossary.py", "--top", "5"]]
    if "--no-build" not in sys.argv:
        steps.append(["checks/build.py"])
    failed = []
    for step in steps:
        print(f"\n=== {' '.join(step)}", flush=True)
        if subprocess.run([sys.executable, str(TOOLS / step[0]), *step[1:]]).returncode:
            failed.append(step[0])
    print(f"\n{'all checks passed' if not failed else 'FAILED: ' + ', '.join(failed)}")
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()
