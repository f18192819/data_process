#!/usr/bin/env python3
"""Second-pass Groq transcription on question-sized derived audio clips."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import time
from datetime import datetime, timezone
from pathlib import Path

import requests

URL = "https://api.groq.com/openai/v1/audio/transcriptions"
MODEL = "whisper-large-v3"
PROMPT = "中文数学解题过程口述。逐字转写，不补充内容。"
CLIPS = {
    "P01": ("第一份/1.m4a", [(1, 0.0, 195.0), (2, 190.0, 275.0), (3, 265.0, 366.037)]),
    "P02": ("第二份/2.m4a", [(1, 0.0, 340.0), (2, 330.0, 650.0), (3, 645.0, 750.190)]),
    "P03": ("第三份/3.m4a", [(1, 0.0, 220.0), (2, 215.0, 560.0), (3, 555.0, 634.137)]),
    "P04": ("第四份/4.m4a", [(1, 0.0, 290.0), (2, 285.0, 375.0), (3, 370.0, 454.784)]),
}


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def dump(value: object, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8")


def call_groq(path: Path, key: str, timeout: int = 900) -> dict:
    with path.open("rb") as f:
        response = requests.post(
            URL,
            headers={"Authorization": f"Bearer {key}"},
            files={"file": (path.name, f, "audio/wav")},
            data=[
                ("model", MODEL), ("language", "zh"), ("prompt", PROMPT),
                ("response_format", "verbose_json"), ("temperature", "0"),
                ("timestamp_granularities[]", "segment"),
                ("timestamp_granularities[]", "word"),
            ],
            timeout=timeout,
        )
    if response.status_code != 200:
        raise RuntimeError(f"Groq HTTP {response.status_code}: {response.text[:1000]}")
    return response.json()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input-dir", required=True, type=Path)
    parser.add_argument("--clip-dir", required=True, type=Path)
    parser.add_argument("--output-dir", required=True, type=Path)
    args = parser.parse_args()
    expected = [args.output_dir / f"{pid}_Q{slot}.raw.json" for pid, (_, specs) in CLIPS.items() for slot, _, _ in specs]
    expected_txt = [path.with_suffix(".txt") for path in expected]
    if all(path.exists() for path in [*expected, *expected_txt]):
        print("[resume] all question-clip transcripts already exist; no API request needed.")
        return 0
    key = os.environ.get("GROQ_API_KEY", "").strip()
    if not key:
        raise SystemExit("GROQ_API_KEY is not set")
    args.clip_dir.mkdir(parents=True, exist_ok=True)
    args.output_dir.mkdir(parents=True, exist_ok=True)
    for pid, (relative, specs) in CLIPS.items():
        source = args.input_dir / Path(relative)
        for slot, start, end in specs:
            wav = args.clip_dir / f"{pid}_Q{slot}.wav"
            output = args.output_dir / f"{pid}_Q{slot}.raw.json"
            txt = args.output_dir / f"{pid}_Q{slot}.raw.txt"
            if output.exists() and txt.exists():
                print(f"[resume] {pid} Q{slot}")
                continue
            if not wav.exists():
                subprocess.run([
                    "ffmpeg", "-hide_banner", "-loglevel", "error", "-y",
                    "-ss", str(start), "-to", str(end), "-i", str(source),
                    "-ac", "1", "-ar", "16000", "-af", "afftdn=nf=-25,dynaudnorm",
                    str(wav),
                ], check=True)
            print(f"[transcribe] {pid} Q{slot} [{start:.3f}, {end:.3f}]", flush=True)
            response = call_groq(wav, key)
            adjusted_segments = []
            for segment in response.get("segments", []):
                item = dict(segment)
                item["clip_start"] = item.get("start")
                item["clip_end"] = item.get("end")
                item["start"] = round(float(item.get("start", 0)) + start, 3)
                item["end"] = round(float(item.get("end", 0)) + start, 3)
                adjusted_segments.append(item)
            adjusted_words = []
            for word in response.get("words", []):
                item = dict(word)
                item["clip_start"] = item.get("start")
                item["clip_end"] = item.get("end")
                item["start"] = round(float(item.get("start", 0)) + start, 3)
                item["end"] = round(float(item.get("end", 0)) + start, 3)
                adjusted_words.append(item)
            payload = {
                "schema_version": "1.0", "participant_id": pid, "question_slot": slot,
                "source_file": str(source.resolve()), "source_sha256": sha256(source),
                "derived_clip": str(wav.resolve()), "derived_clip_sha256": sha256(wav),
                "clip_start_sec": start, "clip_end_sec": end,
                "generated_at": datetime.now(timezone.utc).isoformat(),
                "provider": "groq", "model": MODEL, "prompt": PROMPT,
                "preprocessing": "16 kHz mono WAV; afftdn=nf=-25,dynaudnorm",
                "text": str(response.get("text") or "").strip(),
                "segments": adjusted_segments, "words": adjusted_words,
                "api_response": response,
            }
            dump(payload, output)
            lines = [f"[{s['start']:.2f}-{s['end']:.2f}] {str(s.get('text') or '').strip()}" for s in adjusted_segments]
            txt.write_text("\n".join(lines) + "\n", encoding="utf-8")
            print(f"[ok] {pid} Q{slot}: {len(payload['text'])} chars")
            time.sleep(3.2)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
