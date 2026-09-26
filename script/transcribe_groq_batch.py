#!/usr/bin/env python3
"""Batch-transcribe/import the participant trace pilot with Groq Whisper.

This is adapted from data_collect/my_data/transcribe_groq_free.py.  It never
reads a key from a file: GROQ_API_KEY must be present in the process environment.
Outputs are resume-safe and preserve the complete API response.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import requests

URL = "https://api.groq.com/openai/v1/audio/transcriptions"
MODEL = "whisper-large-v3"
MAX_FILE_BYTES = 25 * 1024 * 1024
PARTICIPANTS = {
    "P01": ("第一份", "1.m4a"),
    "P02": ("第二份", "2.m4a"),
    "P03": ("第三份", "3.m4a"),
    "P04": ("第四份", "4.m4a"),
    "P05": ("第五份", "5.md"),
    "P06": ("第六份", "新测试者_三角函数A组_ThinkAloud整理_Codex.md"),
}
PROMPT = (
    "这是数学解题过程的中文口述录音。请忠实转写实际说出的内容，不要补充、改写、"
    "解释或完善推理。保留犹豫、自我修正、否定、重复、停顿和不知道等表达。"
    "内容可能涉及三角函数或排列组合：阿尔法、贝塔、欧米伽、派、正弦、余弦、正切、"
    "周期、象限、诱导公式、正弦定理、余弦定理、面积、排列、组合、插空、捆绑、补集、"
    "格路、反射、鸽巢、余数、整除、倍数、二进制串。只转写听到的语音。"
)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def dump_json(obj: Any, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(obj, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp.replace(path)


def import_text(participant_id: str, source: Path, output_dir: Path) -> None:
    json_path = output_dir / f"{participant_id}.raw.json"
    txt_path = output_dir / f"{participant_id}.raw.txt"
    if json_path.exists() and txt_path.exists():
        print(f"[resume] {participant_id} already imported")
        return
    text = source.read_text(encoding="utf-8").strip()
    payload = {
        "schema_version": "1.0",
        "participant_id": participant_id,
        "source_file": str(source.resolve()),
        "source_sha256": sha256_file(source),
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "transcript_source": "user_provided_text",
        "tool": "verbatim_text_import",
        "model": None,
        "language": "zh",
        "text": text,
        "segments": [{"id": 1, "start": None, "end": None, "text": text}],
    }
    dump_json(payload, json_path)
    txt_path.write_text(text + "\n", encoding="utf-8")
    print(f"[ok] imported {participant_id} user-provided text")


def request_transcript(
    audio: Path, api_key: str, timeout: int, max_retries: int
) -> dict[str, Any]:
    if audio.stat().st_size > MAX_FILE_BYTES:
        raise RuntimeError(f"{audio.name} exceeds Groq's 25 MB direct-upload limit")
    headers = {"Authorization": f"Bearer {api_key}"}
    last_error = "unknown error"
    for retry in range(max_retries + 1):
        try:
            with audio.open("rb") as handle:
                response = requests.post(
                    URL,
                    headers=headers,
                    files={"file": (audio.name, handle, "application/octet-stream")},
                    data=[
                        ("model", MODEL),
                        ("language", "zh"),
                        ("prompt", PROMPT),
                        ("response_format", "verbose_json"),
                        ("temperature", "0"),
                        ("timestamp_granularities[]", "segment"),
                        ("timestamp_granularities[]", "word"),
                    ],
                    timeout=timeout,
                )
            if response.status_code == 200:
                value = response.json()
                return value if isinstance(value, dict) else {"text": str(value)}
            body = response.text[:1000]
            if response.status_code not in {429, 500, 502, 503, 504}:
                raise RuntimeError(f"Groq HTTP {response.status_code}: {body}")
            last_error = f"Groq HTTP {response.status_code}: {body}"
            retry_after = response.headers.get("retry-after")
            wait = float(retry_after) if retry_after else min(60.0, 5.0 * 2**retry)
        except (requests.ConnectionError, requests.Timeout) as exc:
            last_error = repr(exc)
            wait = min(60.0, 3.0 * 2**retry)
        if retry < max_retries:
            print(f"[retry] {last_error}; waiting {wait:.1f}s", flush=True)
            time.sleep(max(1.0, wait))
    raise RuntimeError(f"Groq transcription failed after retries: {last_error}")


def transcribe_one(
    participant_id: str,
    audio: Path,
    output_dir: Path,
    api_key: str,
    timeout: int,
    max_retries: int,
) -> None:
    json_path = output_dir / f"{participant_id}.raw.json"
    txt_path = output_dir / f"{participant_id}.raw.txt"
    if json_path.exists() and txt_path.exists():
        print(f"[resume] {participant_id} already transcribed")
        return
    print(f"[transcribe] {participant_id}: {audio.name}", flush=True)
    response = request_transcript(audio, api_key, timeout, max_retries)
    text = str(response.get("text") or "").strip()
    payload = {
        "schema_version": "1.0",
        "participant_id": participant_id,
        "source_file": str(audio.resolve()),
        "source_sha256": sha256_file(audio),
        "source_size_bytes": audio.stat().st_size,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "transcript_source": "online_asr",
        "provider": "groq",
        "tool": "Groq speech-to-text REST API",
        "model": MODEL,
        "language": "zh",
        "text": text,
        "segments": response.get("segments", []),
        "words": response.get("words", []),
        "api_response": response,
    }
    dump_json(payload, json_path)
    lines = []
    for segment in payload["segments"]:
        if isinstance(segment, dict):
            lines.append(
                f"[{float(segment.get('start', 0)):.2f}-{float(segment.get('end', 0)):.2f}] "
                f"{str(segment.get('text') or '').strip()}"
            )
    txt_path.write_text(("\n".join(lines) if lines else text) + "\n", encoding="utf-8")
    print(f"[ok] {participant_id}: {len(text)} characters")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input-dir", required=True, type=Path)
    parser.add_argument("--output-dir", required=True, type=Path)
    parser.add_argument("--timeout", type=int, default=600)
    parser.add_argument("--max-retries", type=int, default=6)
    parser.add_argument("--min-interval", type=float, default=3.2)
    args = parser.parse_args()
    input_dir = args.input_dir.resolve()
    output_dir = args.output_dir.resolve()
    output_dir.mkdir(parents=True, exist_ok=True)

    for participant_id in ("P05", "P06"):
        folder, filename = PARTICIPANTS[participant_id]
        import_text(participant_id, input_dir / folder / filename, output_dir)

    pending = [
        participant_id
        for participant_id in list(PARTICIPANTS)[:4]
        if not (output_dir / f"{participant_id}.raw.json").exists()
        or not (output_dir / f"{participant_id}.raw.txt").exists()
    ]
    if not pending:
        print("[resume] P01-P04 transcripts already exist; no API request needed.")
        return 0

    api_key = os.environ.get("GROQ_API_KEY", "").strip()
    if not api_key:
        print("[error] GROQ_API_KEY is not set; P05 import is complete, P01-P04 remain pending.")
        return 2

    failures: list[dict[str, str]] = []
    for index, (participant_id, (folder, filename)) in enumerate(
        list(PARTICIPANTS.items())[:4]
    ):
        try:
            transcribe_one(
                participant_id,
                input_dir / folder / filename,
                output_dir,
                api_key,
                args.timeout,
                args.max_retries,
            )
        except Exception as exc:  # keep other participants resumable
            print(f"[failed] {participant_id}: {exc}", file=sys.stderr)
            failures.append({"participant_id": participant_id, "error": repr(exc)})
        if index < 3:
            time.sleep(args.min_interval)
    dump_json(
        {
            "finished_at": datetime.now(timezone.utc).isoformat(),
            "provider": "groq",
            "model": MODEL,
            "failures": failures,
        },
        output_dir / "transcription_run.json",
    )
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
