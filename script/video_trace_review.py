#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Ephemeral sparse-frame review for f18192819/data_process.

One video at a time:
  list
  prepare --video-id ...
  [optional] zoom --video-id ... --start ... --end ...
  Codex writes trace_replacements.jsonl + review_notes.json
  finalize --video-id ...

finalize validates + applies trace replacements, syncs the main derived files,
logs the review, then deletes ALL temporary frames for that video.

No intermediate video copy is created.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import shutil
import subprocess
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

PARTICIPANT_MAP = {"1": "P05", "2": "P06", "3": "P07", "4": "P08", "5": "P09"}
VIDEO_EXTS = {".mp4", ".mov", ".mkv", ".webm", ".mpeg", ".mpg"}

CORE = Path("data/exports/week3_combinatorics/participant_traces_combinatorics.jsonl")
ANNOTATIONS = Path("data/exports/week3_combinatorics/reviewed_trace_annotations_combinatorics.json")
VARIANTS = Path("data/exports/week3_combinatorics/question_trace_variants_combinatorics.json")
METADATA = Path("data/exports/week3_combinatorics/question_metadata_combinatorics.json")
PRED_DIR = Path("data/exports/week3_combinatorics/prediction_inputs")
MANIFEST = Path("data/exports/week3_combinatorics/transfer_manifest.json")
REVIEW_LOG = Path("data/exports/week3_combinatorics/VIDEO_REVIEW_LOG.jsonl")
BACKUP_DIR = Path("data/exports/week3_combinatorics/backups")
TMP_ROOT = Path(".video_review_tmp")

ALLOWED_STATUS = {"VERBALIZED", "VISUALLY_OBSERVED", "MULTIMODAL_CONFIRMED"}
ALLOWED_CORRECTNESS = {"correct", "partially_correct", "uncertain", "not_applicable"}

def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()

def run(cmd: list[str], capture: bool = False) -> subprocess.CompletedProcess:
    kw: dict[str, Any] = {"check": True, "text": True}
    if capture:
        kw["stdout"] = subprocess.PIPE
        kw["stderr"] = subprocess.PIPE
    return subprocess.run(cmd, **kw)

def need(name: str) -> None:
    if shutil.which(name) is None:
        raise RuntimeError(f"{name} not found on PATH")

def is_lfs_pointer(path: Path) -> bool:
    try:
        return path.stat().st_size < 2048 and path.read_bytes()[:256].startswith(
            b"version https://git-lfs.github.com/spec/v1"
        )
    except OSError:
        return False

def safe_slug(text: str) -> str:
    text = re.sub(r"[^\w\u4e00-\u9fff.-]+", "_", text, flags=re.UNICODE)
    return text.strip("._") or "video"

def infer_group(path: Path) -> str | None:
    if "A组" in path.parts:
        return "COMB_A"
    if "B组" in path.parts:
        return "COMB_B"
    if "C组" in path.parts:
        return "COMB_C"
    return None

def discover_videos(repo: Path) -> list[dict[str, Any]]:
    root = repo / "data" / "raw" / "student_materials"
    out = []
    for student_dir in sorted((p for p in root.iterdir() if p.is_dir()), key=lambda p: p.name):
        student = student_dir.name
        pid = PARTICIPANT_MAP.get(student, f"RAW_{student}")
        candidates = [p for p in student_dir.rglob("*")
                      if p.is_file() and p.suffix.lower() in VIDEO_EXTS]

        # Student 1 has duplicate "-说话人" renders. Prefer ordinary render.
        ordinary = {p.stem for p in candidates if "说话人" not in p.stem}
        filtered = []
        for p in candidates:
            if "说话人" in p.stem:
                base = p.stem.replace("-说话人", "").replace("_说话人", "")
                if base in ordinary:
                    continue
            filtered.append(p)

        for p in sorted(filtered):
            rel = p.relative_to(repo)
            group = infer_group(rel)
            token = group.replace("COMB_", "") if group else "ALL"
            out.append({
                "video_id": safe_slug(f"{pid}__{token}__{p.stem}"),
                "participant_id": pid,
                "student_folder": student,
                "group_hint": group,
                "source_relative_path": rel.as_posix(),
                "lfs_pointer": is_lfs_pointer(p),
            })
    return out

def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))

def write_json(path: Path, obj: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

def load_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    return [json.loads(x) for x in path.read_text(encoding="utf-8").splitlines() if x.strip()]

def write_jsonl(path: Path, rows: Iterable[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="\n") as f:
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")

def duration(video: Path) -> float:
    cp = run([
        "ffprobe", "-v", "error",
        "-show_entries", "format=duration",
        "-of", "default=noprint_wrappers=1:nokey=1",
        str(video)
    ], capture=True)
    return float(cp.stdout.strip())

def extract(video: Path, out_dir: Path, interval: float, max_width: int,
            start: float = 0.0, end: float | None = None) -> list[dict[str, Any]]:
    if interval <= 0:
        raise ValueError("interval must be > 0")
    out_dir.mkdir(parents=True, exist_ok=True)
    cmd = ["ffmpeg", "-y", "-v", "error"]
    if start > 0:
        cmd += ["-ss", f"{start:.3f}"]
    cmd += ["-i", str(video)]
    if end is not None:
        cmd += ["-t", f"{max(0.0, end-start):.3f}"]
    scale = f"scale='min({max_width},iw)':-2" if max_width > 0 else "scale=iw:-2"
    cmd += [
        "-vf", f"fps=fps=1/{interval}:start_time=0,{scale}",
        "-q:v", "5",
        str(out_dir / "frame_%05d.jpg")
    ]
    run(cmd)
    frames = sorted(out_dir.glob("frame_*.jpg"))
    return [{
        "frame_file": p.relative_to(out_dir.parent.parent).as_posix(),
        "sample_time_sec": round(start + i * interval, 3),
        "sampling_interval_sec": interval
    } for i, p in enumerate(frames)]

def find_video(videos: list[dict[str, Any]], video_id: str) -> dict[str, Any]:
    for v in videos:
        if v["video_id"] == video_id:
            return v
    raise KeyError(f"Unknown video_id: {video_id}")

def linked_traces(traces: list[dict[str, Any]], info: dict[str, Any]) -> list[dict[str, Any]]:
    rows = [t for t in traces if t.get("participant_id") == info["participant_id"]]
    if info.get("group_hint"):
        rows = [t for t in rows if t.get("assigned_group") == info["group_hint"]]
    return sorted(rows, key=lambda t: (t.get("assigned_group", ""), t.get("question_slot", 99)))

def ensure_one_workspace(repo: Path) -> None:
    root = repo / TMP_ROOT
    if not root.exists():
        return
    active = [p.name for p in root.iterdir() if p.is_dir()]
    if active:
        raise RuntimeError(
            "Existing temporary review workspace: " + ", ".join(active) +
            ". Finalize or cleanup before preparing another video."
        )

def cmd_list(repo: Path) -> int:
    traces = load_jsonl(repo / CORE)
    for v in discover_videos(repo):
        print(json.dumps({
            **v,
            "linked_trace_ids": [t["trace_id"] for t in linked_traces(traces, v)]
        }, ensure_ascii=False))
    return 0

def cmd_prepare(repo: Path, video_id: str, interval: float, max_width: int) -> int:
    need("ffmpeg"); need("ffprobe")
    ensure_one_workspace(repo)
    info = find_video(discover_videos(repo), video_id)
    source = repo / info["source_relative_path"]
    if is_lfs_pointer(source):
        raise RuntimeError(f"{source} is a Git LFS pointer. Run `git lfs pull` first.")

    traces = load_jsonl(repo / CORE)
    linked = linked_traces(traces, info)
    work = repo / TMP_ROOT / video_id
    d = duration(source)
    frames = extract(source, work / "frames", interval, max_width, 0.0, d)
    manifest = {
        "schema_version": "1.0",
        "created_at": now_iso(),
        "video": info,
        "duration_sec": round(d, 3),
        "sampling": {"base_interval_sec": interval, "max_width": max_width,
                     "frame_count": len(frames)},
        "frames": frames,
        "zoom_windows": [],
        "linked_trace_ids": [t["trace_id"] for t in linked],
        "research_warning": (
            "Use frames only for visible writing/diagram/cross-out/question-boundary evidence. "
            "Do not infer unspoken cognition or emotion from face/posture."
        )
    }
    write_json(work / "frame_manifest.json", manifest)
    write_jsonl(work / "linked_traces.jsonl", linked)
    (work / "README_FOR_CODEX.md").write_text(
        f"""# Temporary review workspace

Video: `{video_id}`
Source: `{info['source_relative_path']}`
Participant: `{info['participant_id']}`
Base interval: {interval}s

Linked traces:
{chr(10).join("- " + t["trace_id"] for t in linked) if linked else "- none"}

Review frames, optionally call `zoom`, then write:
- `trace_replacements.jsonl` (FULL trace objects, changed traces only)
- `review_notes.json`
- optional `segment_updates.json`

Then run:
`python video_trace_review.py finalize --video-id "{video_id}"`

Successful finalize deletes this whole temporary workspace.
""",
        encoding="utf-8"
    )
    print(f"[READY] {work}")
    print(f"[FRAMES] {len(frames)}")
    return 0

def cmd_zoom(repo: Path, video_id: str, start: float, end: float,
             interval: float, max_width: int) -> int:
    if end <= start:
        raise ValueError("end must be > start")
    work = repo / TMP_ROOT / video_id
    mp = work / "frame_manifest.json"
    if not mp.exists():
        raise RuntimeError("Prepare the video first.")
    manifest = load_json(mp)
    source = repo / manifest["video"]["source_relative_path"]
    d = float(manifest["duration_sec"])
    start = max(0.0, start); end = min(d, end)
    label = safe_slug(f"zoom_{start:.1f}_{end:.1f}_{interval:.1f}s")
    frames = extract(source, work / "zoom" / label, interval, max_width, start, end)
    manifest["zoom_windows"].append({
        "label": label, "start_sec": start, "end_sec": end,
        "interval_sec": interval, "frames": frames
    })
    write_json(mp, manifest)
    print(f"[ZOOM READY] {len(frames)} frames")
    return 0

def validate_trace(t: dict[str, Any]) -> list[str]:
    errors = []
    required = ["trace_id","question_id","question_slot","trace_confidence",
                "first_attention","strategy","path_signature","steps",
                "analyst_inferences","participant_id","assigned_group"]
    for k in required:
        if k not in t:
            errors.append(f"missing key: {k}")
    steps = t.get("steps") or []
    sig = t.get("path_signature") or []
    if len(steps) != len(sig):
        errors.append("path_signature length != steps length")
    prev = -1e100
    ids = set()
    for i, s in enumerate(steps, 1):
        sid = s.get("step_id")
        if not sid: errors.append(f"step {i}: missing step_id")
        elif sid in ids: errors.append(f"step {i}: duplicate step_id {sid}")
        ids.add(sid)
        st = s.get("start_sec")
        if not isinstance(st, (int,float)):
            errors.append(f"step {i}: start_sec not numeric")
        elif st < prev:
            errors.append(f"step {i}: nonmonotonic time")
        else:
            prev = float(st)
        if s.get("status") not in ALLOWED_STATUS:
            errors.append(f"step {i}: bad status {s.get('status')!r}")
        if s.get("correctness") not in ALLOWED_CORRECTNESS:
            errors.append(f"step {i}: bad correctness {s.get('correctness')!r}")
        c = s.get("confidence")
        if not isinstance(c,(int,float)) or not 0 <= float(c) <= 1:
            errors.append(f"step {i}: bad confidence")
        if s.get("status") in {"VISUALLY_OBSERVED","MULTIMODAL_CONFIRMED"} and not s.get("visual_evidence"):
            errors.append(f"step {i}: visual status requires visual_evidence")
    return errors

def longest_common_prefix(paths: list[list[str]]) -> list[str]:
    if not paths: return []
    out = []
    for vals in zip(*paths):
        if len(set(vals)) != 1: break
        out.append(vals[0])
    return out

def build_variants(traces: list[dict[str, Any]], metadata: dict[str, Any]) -> dict[str, Any]:
    group_lookup = {q["question_id"]: g["group_id"]
                    for g in metadata["groups"] for q in g["questions"]}
    by_q: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for t in traces:
        by_q[t["question_id"]].append(t)
    questions = []
    for qid in sorted(by_q):
        items = sorted(by_q[qid], key=lambda x: x["participant_id"])
        sg: dict[str, list[dict[str, Any]]] = defaultdict(list)
        for t in items: sg[t["strategy"]].append(t)
        families = []
        for idx,(strategy,members) in enumerate(sg.items(),1):
            rep = members[0]
            families.append({
                "family_id": f"T{idx}",
                "label": strategy.replace("_"," "),
                "strategy": strategy,
                "participants": [m["participant_id"] for m in members],
                "signature": rep["path_signature"],
                "participant_signatures": {m["participant_id"]:m["path_signature"] for m in members},
                "core_steps": [s["content"] for s in rep["steps"]],
                "core_step_evidence": [{
                    "participant_id": rep["participant_id"],
                    "content": s["content"], "evidence_text": s["evidence_text"],
                    "start_sec": s["start_sec"], "end_sec": s.get("end_sec"),
                    "status": s["status"], "confidence": s["confidence"]
                } for s in rep["steps"]],
                "participant_paths": {m["participant_id"]:[{
                    "content": s["content"], "evidence_text": s["evidence_text"],
                    "start_sec": s["start_sec"], "end_sec": s.get("end_sec"),
                    "status": s["status"], "confidence": s["confidence"]
                } for s in m["steps"]] for m in members},
                "representative_evidence": [{
                    "participant_id": m["participant_id"],
                    "evidence": m["steps"][0]["evidence_text"] if m.get("steps") else ""
                } for m in members]
            })
        prefix = longest_common_prefix([t["path_signature"] for t in items])
        if len(items)<2:
            div = "少于两条 observed trace，无法估计分叉点。"
        elif all(t["path_signature"]==items[0]["path_signature"] for t in items[1:]):
            div = "当前 observed traces 的动作路径相同，未观察到动作级分叉。"
        else:
            lead = ("共同前缀 "+" / ".join(prefix)+" 之后分叉：" if prefix else "入口即分叉：")
            branches=[]
            for t in items:
                nxt=t["path_signature"][len(prefix)] if len(t["path_signature"])>len(prefix) else "[路径结束]"
                branches.append(f"{t['participant_id']} 进入 {nxt}")
            div=lead+"；".join(branches)+"。"
        questions.append({
            "question_id": qid, "group_id": group_lookup.get(qid),
            "n_participants": len(items), "valid_traces": len(items),
            "low_confidence_traces": sum(float(t.get("trace_confidence",0))<0.75 for t in items),
            "participants": [t["participant_id"] for t in items],
            "trace_families": families, "common_prefix": prefix,
            "first_meaningful_divergence": div
        })
    return {"schema_version":"1.0","generated_at":now_iso(),"questions":questions}

def sync_annotations(repo: Path, traces: list[dict[str, Any]], info: dict[str, Any]) -> None:
    p = repo / ANNOTATIONS
    if not p.exists(): return
    a = load_json(p)
    by_p: dict[str,list[dict[str,Any]]] = defaultdict(list)
    for t in traces: by_p[t["participant_id"]].append(t)
    for pid, rows in by_p.items():
        part = a.get("participants",{}).get(pid)
        if not part: continue
        part["traces"]=[{k:v for k,v in t.items() if k not in {"participant_id","assigned_group"}}
                        for t in sorted(rows,key=lambda x:(x.get("assigned_group",""),x.get("question_slot",99)))]
        reviewed = part.setdefault("video_reviewed_sources",[])
        src=info["source_relative_path"]
        if src not in reviewed: reviewed.append(src)
    write_json(p,a)

def apply_segment_updates(repo: Path, work: Path) -> None:
    up = work / "segment_updates.json"
    if not up.exists(): return
    updates=load_json(up)
    if not isinstance(updates,list): raise ValueError("segment_updates.json must be array")
    p=repo/ANNOTATIONS; a=load_json(p)
    for u in updates:
        part=a["participants"][u["participant_id"]]
        found=False
        for seg in part.get("segments",[]):
            if seg.get("question_id")==u["question_id"]:
                for k in ["start_sec","end_sec","boundary_confidence","boundary_rationale"]:
                    if k in u: seg[k]=u[k]
                found=True; break
        if not found: raise KeyError(f"No segment {u['participant_id']} {u['question_id']}")
    write_json(p,a)

def sync_prediction_inputs(repo: Path, traces: list[dict[str, Any]]) -> None:
    d=repo/PRED_DIR; d.mkdir(parents=True,exist_ok=True)
    by_p: dict[str,list[dict[str,Any]]] = defaultdict(list)
    for t in traces:
        if t.get("assigned_group")=="COMB_A": by_p[t["participant_id"]].append(t)
    for pid,rows in by_p.items():
        rows=sorted(rows,key=lambda x:x.get("question_slot",99))
        write_json(d/f"{pid}_from_A.json",{
            "schema_version":"1.0","participant_id":pid,
            "input_group":"COMB_A","target_group":"COMB_B",
            "blindness_note":"This file contains no current-participant B transcript, B trace, or B outcome.",
            "a_group_observations":[{
                "question_id":t["question_id"],"first_attention":t["first_attention"],
                "strategy":t["strategy"],"path_signature":t["path_signature"],
                "observed_steps":t["steps"],"analyst_inferences":t["analyst_inferences"]
            } for t in rows]
        })

def sha256(path: Path) -> str:
    h=hashlib.sha256()
    with path.open("rb") as f:
        for b in iter(lambda:f.read(1024*1024),b""): h.update(b)
    return h.hexdigest()

def sync_manifest(repo: Path, traces: list[dict[str, Any]]) -> None:
    out=repo/"data/exports/week3_combinatorics"
    files=sorted(p for p in out.rglob("*") if p.is_file()
                 and p.name!="transfer_manifest.json" and "backups" not in p.parts)
    pred=list((repo/PRED_DIR).glob("*_from_A.json"))
    write_json(repo/MANIFEST,{
        "schema_version":"1.0","generated_at":now_iso(),"source_repo":str(repo),
        "counts":{
            "participants":len({t["participant_id"] for t in traces}),
            "traces":len(traces),
            "questions_covered":len({t["question_id"] for t in traces}),
            "observed_steps":sum(len(t.get("steps",[])) for t in traces),
            "low_confidence_steps":sum(1 for t in traces for s in t.get("steps",[])
                                       if isinstance(s.get("confidence"),(int,float)) and s["confidence"]<0.75),
            "prediction_inputs":len(pred)
        },
        "participants":sorted({t["participant_id"] for t in traces}),
        "prediction_input_participants":sorted(p.stem.replace("_from_A","") for p in pred),
        "files":[{"path":p.relative_to(out).as_posix(),"size_bytes":p.stat().st_size,"sha256":sha256(p)}
                 for p in files]
    })

def append_log(repo: Path, video_id: str, manifest: dict[str,Any],
               notes: dict[str,Any], changed: list[str]) -> None:
    p=repo/REVIEW_LOG
    with p.open("a",encoding="utf-8",newline="\n") as f:
        f.write(json.dumps({
            "reviewed_at":now_iso(),"video_id":video_id,
            "source_relative_path":manifest["video"]["source_relative_path"],
            "participant_id":manifest["video"]["participant_id"],
            "base_sampling_interval_sec":manifest["sampling"]["base_interval_sec"],
            "zoom_windows":[{
                "start_sec":z["start_sec"],"end_sec":z["end_sec"],"interval_sec":z["interval_sec"]
            } for z in manifest.get("zoom_windows",[])],
            "changed_trace_ids":changed,"review_notes":notes,
            "frames_deleted_after_finalize":True
        },ensure_ascii=False)+"\n")

def cmd_finalize(repo: Path, video_id: str) -> int:
    work=repo/TMP_ROOT/video_id
    mp=work/"frame_manifest.json"
    if not mp.exists(): raise RuntimeError("No prepared workspace")
    manifest=load_json(mp)
    linked=set(manifest.get("linked_trace_ids",[]))
    core=repo/CORE
    canonical=load_jsonl(core)
    by_id={t["trace_id"]:t for t in canonical}
    repl=load_jsonl(work/"trace_replacements.jsonl") if (work/"trace_replacements.jsonl").exists() else []
    ids=[t.get("trace_id") for t in repl]
    if len(ids)!=len(set(ids)): raise ValueError("duplicate trace_id in replacements")

    for r in repl:
        tid=r.get("trace_id")
        if tid not in linked: raise ValueError(f"{tid} is not linked to this video")
        old=by_id[tid]
        for k in ["trace_id","participant_id","question_id","assigned_group"]:
            if r.get(k)!=old.get(k): raise ValueError(f"{tid}: immutable field changed: {k}")
        errs=validate_trace(r)
        if errs: raise ValueError(f"{tid} validation failed:\n- "+"\n- ".join(errs))
        r["source_modalities"]=list(dict.fromkeys(list(r.get("source_modalities",[]))+["video_frames"]))
        r["video_review"]={
            "reviewed_at":now_iso(),
            "source_relative_path":manifest["video"]["source_relative_path"],
            "sampling_interval_sec":manifest["sampling"]["base_interval_sec"],
            "ephemeral_frames_deleted_after_finalize":True
        }
        by_id[tid]=r

    updated=[by_id[t["trace_id"]] for t in canonical]
    global_errors=[]
    for t in updated:
        for e in validate_trace(t): global_errors.append(f"{t['trace_id']}: {e}")
    if global_errors: raise ValueError("Global validation failed:\n- "+"\n- ".join(global_errors))

    bd=repo/BACKUP_DIR; bd.mkdir(parents=True,exist_ok=True)
    stamp=datetime.now().strftime("%Y%m%d_%H%M%S")
    shutil.copy2(core,bd/f"participant_traces_before_{video_id}_{stamp}.jsonl")

    temp=core.with_suffix(".jsonl.tmp")
    write_jsonl(temp,updated); temp.replace(core)
    sync_annotations(repo,updated,manifest["video"])
    apply_segment_updates(repo,work)
    write_json(repo/VARIANTS,build_variants(updated,load_json(repo/METADATA)))
    sync_prediction_inputs(repo,updated)

    notes=load_json(work/"review_notes.json") if (work/"review_notes.json").exists() else {
        "usefulness":"unknown","summary":"No review_notes.json supplied.","observations":[]
    }
    append_log(repo,video_id,manifest,notes,[t["trace_id"] for t in repl])
    sync_manifest(repo,updated)

    shutil.rmtree(work)
    root=repo/TMP_ROOT
    if root.exists() and not any(root.iterdir()): root.rmdir()
    print(f"[FINALIZED] {video_id}")
    print(f"[CHANGED TRACES] {len(repl)}")
    print("[CLEANUP] all extracted frames and temporary review files deleted")
    return 0

def cmd_cleanup(repo: Path, video_id: str | None, all_: bool) -> int:
    root=repo/TMP_ROOT
    if not root.exists():
        print("[CLEAN] no temp workspace"); return 0
    if all_:
        shutil.rmtree(root); print("[CLEAN] removed all temp review files"); return 0
    if not video_id: raise ValueError("provide --video-id or --all")
    work=root/video_id
    if work.exists(): shutil.rmtree(work)
    if root.exists() and not any(root.iterdir()): root.rmdir()
    print(f"[CLEAN] {video_id}")
    return 0

def main() -> int:
    ap=argparse.ArgumentParser()
    ap.add_argument("--repo-root",type=Path,default=Path("."))
    sub=ap.add_subparsers(dest="cmd",required=True)
    sub.add_parser("list")
    p=sub.add_parser("prepare")
    p.add_argument("--video-id",required=True); p.add_argument("--interval",type=float,default=10.0)
    p.add_argument("--max-width",type=int,default=1280)
    z=sub.add_parser("zoom")
    z.add_argument("--video-id",required=True); z.add_argument("--start",type=float,required=True)
    z.add_argument("--end",type=float,required=True); z.add_argument("--interval",type=float,default=1.0)
    z.add_argument("--max-width",type=int,default=1600)
    f=sub.add_parser("finalize"); f.add_argument("--video-id",required=True)
    c=sub.add_parser("cleanup"); c.add_argument("--video-id"); c.add_argument("--all",action="store_true")
    a=ap.parse_args(); repo=a.repo_root.resolve()
    if not (repo/"data/raw/student_materials").exists():
        raise RuntimeError("Run from data_process repo root or use --repo-root")
    if a.cmd=="list": return cmd_list(repo)
    if a.cmd=="prepare": return cmd_prepare(repo,a.video_id,a.interval,a.max_width)
    if a.cmd=="zoom": return cmd_zoom(repo,a.video_id,a.start,a.end,a.interval,a.max_width)
    if a.cmd=="finalize": return cmd_finalize(repo,a.video_id)
    if a.cmd=="cleanup": return cmd_cleanup(repo,a.video_id,a.all)
    return 1

if __name__=="__main__":
    raise SystemExit(main())
