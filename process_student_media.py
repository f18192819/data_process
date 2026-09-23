#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Audio-first preprocessing for f18192819/data_process.

Default behavior:
- DO NOT process 学生素材/1 media. Student 1 already has timestamped transcripts:
  学生素材/1/A组/原文.md
  学生素材/1/B组/原文.md
- Process 学生素材/2, /3, /4, /5.
- For student 3, process audio.m4a ONLY. Ignore video-front.mp4 and ink.points.bin for now.
- For students 2 and 4, extract audio from MP4.
- For student 5, transcribe A1.m4a/A2.m4a/A3.m4a directly.
- Normalize all audio to 16 kHz mono FLAC.
- Chunk long audio with overlap.
- Transcribe with Groq Whisper using segment timestamps.
- Write JSONL transcripts for later Codex structuring.

IMPORTANT:
Never hard-code GROQ_API_KEY in this file.
Use the GROQ_API_KEY environment variable.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import time
from dataclasses import dataclass, asdict
from difflib import SequenceMatcher
from pathlib import Path
from typing import Any, Iterable

try:
    from groq import Groq
except ImportError:
    Groq = None

MEDIA_EXTS = {".mp4", ".m4a", ".mp3", ".wav", ".flac", ".ogg", ".webm", ".mpeg", ".mpga"}
VIDEO_EXTS = {".mp4", ".webm", ".mpeg"}

DEFAULT_STUDENTS = ["2", "3", "4", "5"]
DEFAULT_PARTICIPANT_MAP = {
    "1": "P05",  # transcript only; not ASR
    "2": "P06",
    "3": "P07",
    "4": "P08",
    "5": "P09",
}

ASR_PROMPT = (
    "大学组合数学 Think-Aloud 解题录音。"
    "术语可能包括：排列组合、组合数、排列数、插空法、捆绑法、补集、"
    "格路、反射原理、卡特兰数、鸽巢原理、抽屉原理、同余、模10、整除、"
    "动态规划、递归、m、n、a、b。请忠实转写，不要改写学生的数学推理。"
)

@dataclass
class SourceRecord:
    student_folder: str
    participant_id: str
    source_relative_path: str
    source_type: str
    group_hint: str | None
    question_hint: str | None
    lfs_pointer: bool = False

def run(cmd: list[str], capture: bool = False) -> subprocess.CompletedProcess:
    kwargs = {"check": True, "text": True}
    if capture:
        kwargs["stdout"] = subprocess.PIPE
        kwargs["stderr"] = subprocess.PIPE
    return subprocess.run(cmd, **kwargs)

def check_binary(name: str) -> None:
    if shutil.which(name) is None:
        raise RuntimeError(f"Required executable not found on PATH: {name}")

def parse_participant_map(spec: str | None) -> dict[str, str]:
    mapping = dict(DEFAULT_PARTICIPANT_MAP)
    if spec:
        for item in spec.split(","):
            if not item.strip():
                continue
            raw, pid = item.split("=", 1)
            mapping[raw.strip()] = pid.strip()
    return mapping

def is_git_lfs_pointer(path: Path) -> bool:
    try:
        return path.stat().st_size < 2048 and path.read_bytes()[:256].startswith(
            b"version https://git-lfs.github.com/spec/v1"
        )
    except OSError:
        return False

def safe_slug(text: str) -> str:
    text = re.sub(r"[^\w\u4e00-\u9fff.-]+", "_", text, flags=re.UNICODE)
    return text.strip("._") or "session"

def infer_hints(relative_path: Path) -> tuple[str | None, str | None]:
    parts = list(relative_path.parts)
    group_hint = None
    question_hint = None

    if "A组" in parts:
        group_hint = "COMB_A"
    elif "B组" in parts:
        group_hint = "COMB_B"
    elif "C组" in parts:
        group_hint = "COMB_C"

    stem = relative_path.stem.upper()
    m = re.match(r"^([ABC])([123])(?:$|[_\-.])", stem)
    if m:
        group_hint = f"COMB_{m.group(1)}"
        question_hint = f"COMB_{m.group(1)}{m.group(2)}"

    return group_hint, question_hint

def discover_media(
    repo_root: Path,
    students: list[str],
    participant_map: dict[str, str],
) -> list[SourceRecord]:
    root = repo_root / "学生素材"
    records: list[SourceRecord] = []

    for student in students:
        student_dir = root / student
        if not student_dir.exists():
            print(f"[WARN] missing folder: {student_dir}", file=sys.stderr)
            continue

        pid = participant_map.get(student, f"RAW_{student}")
        candidates = [
            p for p in student_dir.rglob("*")
            if p.is_file() and p.suffix.lower() in MEDIA_EXTS
        ]

        # Current experiment decision:
        # Student 3: audio only, ignore front camera video.
        if student == "3":
            candidates = [
                p for p in candidates
                if p.name.lower() == "audio.m4a" or p.suffix.lower() in {".wav", ".flac", ".mp3", ".m4a"}
            ]

        for p in sorted(candidates):
            rel = p.relative_to(repo_root)
            gh, qh = infer_hints(rel)
            records.append(SourceRecord(
                student_folder=student,
                participant_id=pid,
                source_relative_path=str(rel),
                source_type="video" if p.suffix.lower() in VIDEO_EXTS else "audio",
                group_hint=gh,
                question_hint=qh,
                lfs_pointer=is_git_lfs_pointer(p),
            ))
    return records

def ffprobe_duration(path: Path) -> float:
    cp = run([
        "ffprobe", "-v", "error",
        "-show_entries", "format=duration",
        "-of", "default=noprint_wrappers=1:nokey=1",
        str(path)
    ], capture=True)
    return float(cp.stdout.strip())

def normalize_audio(source: Path, output_flac: Path) -> None:
    output_flac.parent.mkdir(parents=True, exist_ok=True)
    run([
        "ffmpeg", "-y", "-v", "error",
        "-i", str(source),
        "-map", "0:a:0",
        "-ar", "16000",
        "-ac", "1",
        "-c:a", "flac",
        str(output_flac),
    ])

def make_chunks(audio: Path, chunks_dir: Path, chunk_seconds: float, overlap_seconds: float):
    chunks_dir.mkdir(parents=True, exist_ok=True)
    duration = ffprobe_duration(audio)

    if duration <= chunk_seconds:
        out = chunks_dir / "chunk_000.flac"
        shutil.copy2(audio, out)
        return [{"index": 0, "start_sec": 0.0, "end_sec": duration, "path": str(out)}]

    if overlap_seconds < 0 or overlap_seconds >= chunk_seconds:
        raise ValueError("Require 0 <= overlap_seconds < chunk_seconds")

    step = chunk_seconds - overlap_seconds
    chunks = []
    start = 0.0
    idx = 0
    while start < duration - 0.05:
        length = min(chunk_seconds, duration - start)
        out = chunks_dir / f"chunk_{idx:03d}.flac"
        run([
            "ffmpeg", "-y", "-v", "error",
            "-ss", f"{start:.3f}",
            "-i", str(audio),
            "-t", f"{length:.3f}",
            "-ar", "16000", "-ac", "1", "-c:a", "flac",
            str(out),
        ])
        chunks.append({
            "index": idx,
            "start_sec": start,
            "end_sec": min(duration, start + length),
            "path": str(out),
        })
        idx += 1
        start += step
    return chunks

def obj_to_dict(obj: Any) -> Any:
    if hasattr(obj, "model_dump"):
        return obj.model_dump()
    if hasattr(obj, "dict"):
        return obj.dict()
    if isinstance(obj, dict):
        return obj
    return json.loads(json.dumps(obj, default=str))

def transcribe(client: Any, chunk: Path, model: str, language: str, word_timestamps: bool):
    granularities = ["segment", "word"] if word_timestamps else ["segment"]
    with chunk.open("rb") as f:
        result = client.audio.transcriptions.create(
            file=f,
            model=model,
            language=language,
            prompt=ASR_PROMPT,
            response_format="verbose_json",
            timestamp_granularities=granularities,
            temperature=0.0,
        )
    return obj_to_dict(result)

def norm_text(text: str) -> str:
    return re.sub(r"\s+", "", text or "").lower()

def dedupe_segments(segments: list[dict[str, Any]]) -> list[dict[str, Any]]:
    segments = sorted(segments, key=lambda s: (s["start_sec"], s["end_sec"]))
    out: list[dict[str, Any]] = []

    for seg in segments:
        if not out:
            out.append(seg)
            continue

        prev = out[-1]
        ov_start = max(prev["start_sec"], seg["start_sec"])
        ov_end = min(prev["end_sec"], seg["end_sec"])
        overlap = max(0.0, ov_end - ov_start)
        denom = max(0.001, min(
            prev["end_sec"] - prev["start_sec"],
            seg["end_sec"] - seg["start_sec"],
        ))
        overlap_ratio = overlap / denom
        sim = SequenceMatcher(None, norm_text(prev["text"]), norm_text(seg["text"])).ratio()

        if overlap_ratio >= 0.45 and sim >= 0.55:
            p = prev.get("avg_logprob")
            q = seg.get("avg_logprob")
            if isinstance(q, (int, float)) and (not isinstance(p, (int, float)) or q > p):
                out[-1] = seg
            continue
        out.append(seg)

    for i, seg in enumerate(out, 1):
        seg["segment_id"] = f"seg_{i:04d}"
    return out

def write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")

def write_jsonl(path: Path, rows: Iterable[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")

def process_one(
    repo_root: Path,
    output_root: Path,
    rec: SourceRecord,
    client: Any | None,
    model: str,
    language: str,
    chunk_seconds: float,
    overlap_seconds: float,
    word_timestamps: bool,
    extract_only: bool,
    force: bool,
) -> dict[str, Any]:
    source = repo_root / rec.source_relative_path
    slug = safe_slug(f"{rec.participant_id}__{source.parent.name}__{source.stem}")
    session_dir = output_root / rec.participant_id / "sessions" / slug
    transcript_path = session_dir / "transcript_segments.jsonl"

    if transcript_path.exists() and not force:
        return {"status": "skipped_existing", "source": rec.source_relative_path}

    if is_git_lfs_pointer(source):
        msg = {
            "status": "error_git_lfs_pointer",
            "source": asdict(rec),
            "message": "Run `git lfs pull` and rerun."
        }
        write_json(session_dir / "session_manifest.json", msg)
        return msg

    audio = session_dir / "audio" / "normalized_16k_mono.flac"
    normalize_audio(source, audio)
    duration = ffprobe_duration(audio)

    chunks = make_chunks(audio, session_dir / "chunks", chunk_seconds, overlap_seconds)

    manifest = {
        "status": "audio_extracted" if extract_only else "transcribing",
        "source": asdict(rec),
        "duration_sec": round(duration, 3),
        "audio_path": str(audio.relative_to(session_dir)),
        "chunks": [{**c, "path": str(Path(c["path"]).relative_to(session_dir))} for c in chunks],
    }
    write_json(session_dir / "session_manifest.json", manifest)

    if extract_only:
        return {"status": "audio_extracted", "source": rec.source_relative_path}

    all_segments = []
    raw_dir = session_dir / "raw_groq"
    raw_dir.mkdir(parents=True, exist_ok=True)

    for chunk in chunks:
        print(f"[ASR] {rec.participant_id} {source.name} chunk={chunk['index']}")
        response = transcribe(client, Path(chunk["path"]), model, language, word_timestamps)
        write_json(raw_dir / f"chunk_{chunk['index']:03d}.json", response)

        offset = float(chunk["start_sec"])
        for raw_seg in response.get("segments") or []:
            s = obj_to_dict(raw_seg)
            text = (s.get("text") or "").strip()
            if not text:
                continue
            avg = s.get("avg_logprob")
            nsp = s.get("no_speech_prob")
            review_required = (
                (isinstance(avg, (int, float)) and avg < -0.55)
                or (isinstance(nsp, (int, float)) and nsp > 0.35)
            )
            all_segments.append({
                "segment_id": None,
                "start_sec": round(offset + float(s.get("start", 0)), 3),
                "end_sec": round(offset + float(s.get("end", 0)), 3),
                "text": text,
                "avg_logprob": avg,
                "no_speech_prob": nsp,
                "compression_ratio": s.get("compression_ratio"),
                "review_required": review_required,
                "status": "RAW_ASR",
                "participant_id": rec.participant_id,
                "group_hint": rec.group_hint,
                "question_hint": rec.question_hint,
                "source_relative_path": rec.source_relative_path,
                "asr_model": model,
            })

    segments = dedupe_segments(all_segments)
    write_jsonl(transcript_path, segments)

    with (session_dir / "transcript.txt").open("w", encoding="utf-8") as f:
        for s in segments:
            flag = " [REVIEW]" if s["review_required"] else ""
            f.write(f"[{s['start_sec']:8.3f}-{s['end_sec']:8.3f}]{flag} {s['text']}\n")

    manifest["status"] = "complete"
    manifest["asr"] = {
        "provider": "Groq",
        "model": model,
        "language": language,
        "timestamp_granularities": ["segment", "word"] if word_timestamps else ["segment"],
        "segment_count": len(segments),
        "review_required_count": sum(1 for s in segments if s["review_required"]),
    }
    write_json(session_dir / "session_manifest.json", manifest)

    return {
        "status": "complete",
        "participant_id": rec.participant_id,
        "source": rec.source_relative_path,
        "duration_sec": round(duration, 3),
        "segment_count": len(segments),
        "session_dir": str(session_dir.relative_to(output_root)),
    }

def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo-root", type=Path, default=Path("."))
    parser.add_argument("--output-root", type=Path, default=Path("音频转写_待结构化"))
    parser.add_argument("--students", nargs="+", default=DEFAULT_STUDENTS)
    parser.add_argument("--participant-map", default=None)
    parser.add_argument("--model", default="whisper-large-v3")
    parser.add_argument("--language", default="zh")
    parser.add_argument("--chunk-seconds", type=float, default=480.0)
    parser.add_argument("--overlap-seconds", type=float, default=3.0)
    parser.add_argument("--word-timestamps", action="store_true")
    parser.add_argument("--extract-only", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()

    repo_root = args.repo_root.resolve()
    output_root = args.output_root
    if not output_root.is_absolute():
        output_root = (repo_root / output_root).resolve()

    check_binary("ffmpeg")
    check_binary("ffprobe")

    participant_map = parse_participant_map(args.participant_map)
    records = discover_media(repo_root, args.students, participant_map)

    output_root.mkdir(parents=True, exist_ok=True)
    write_json(output_root / "media_inventory.json", {
        "note": "Student 1 media intentionally skipped; use 学生素材/1/A组/原文.md and B组/原文.md.",
        "students_processed_by_asr": args.students,
        "participant_map": participant_map,
        "records": [asdict(r) for r in records],
    })

    print(f"[INFO] discovered {len(records)} media files")
    for r in records:
        print(f"  {r.participant_id}: {r.source_relative_path}"
              f" group={r.group_hint} question={r.question_hint}"
              f"{' [LFS POINTER]' if r.lfs_pointer else ''}")

    if args.dry_run:
        return 0

    if args.extract_only:
        client = None
    else:
        if Groq is None:
            raise RuntimeError("Install dependency: pip install groq")
        if not os.environ.get("GROQ_API_KEY"):
            raise RuntimeError("Missing GROQ_API_KEY environment variable.")
        client = Groq(api_key=os.environ["GROQ_API_KEY"])

    results = []
    for rec in records:
        try:
            results.append(process_one(
                repo_root, output_root, rec, client,
                args.model, args.language,
                args.chunk_seconds, args.overlap_seconds,
                args.word_timestamps, args.extract_only, args.force
            ))
        except Exception as e:
            print(f"[ERROR] {rec.source_relative_path}: {e}", file=sys.stderr)
            results.append({
                "status": "error",
                "participant_id": rec.participant_id,
                "source": rec.source_relative_path,
                "error": repr(e),
            })

    write_json(output_root / "processing_summary.json", {
        "generated_at_unix": time.time(),
        "model": args.model,
        "results": results,
    })
    print(f"[DONE] {output_root}")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
