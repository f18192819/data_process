#!/usr/bin/env python3
"""One-command resumable entry point for the student-trace pilot."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path


def run(command: list[str], cwd: Path) -> None:
    print("+", " ".join(command), flush=True)
    subprocess.run(command, cwd=cwd, check=True)


def main() -> int:
    repo = Path(__file__).resolve().parent.parent
    python = sys.executable
    run([
        python, "script/transcribe_groq_batch.py",
        "--input-dir", "收集数据结果",
        "--output-dir", "data/interim/transcripts_raw",
    ], repo)
    run([
        python, "script/transcribe_question_clips_groq.py",
        "--input-dir", "收集数据结果",
        "--clip-dir", "data/interim/asr_clips",
        "--output-dir", "data/interim/transcripts_raw_resegmented",
    ], repo)
    run([
        python, "script/build_student_traces.py",
        "--input", "收集数据结果.zip",
        "--question-bank", "configs/question_bank_selected.json",
        "--output", "data/processed/trace_pilot",
    ], repo)
    run([python, "-m", "unittest", "discover", "-s", "tests", "-v"], repo)
    print("Primary report: reports/by_question_trace_report.md")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
