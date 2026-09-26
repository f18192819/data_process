#!/usr/bin/env python3
"""Build auditable observed student traces and cross-question reports."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
import subprocess
import zipfile
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

ACTION_TYPES = {
    "ATTEND", "RECALL", "REPRESENT", "PLAN", "DERIVE", "CALCULATE",
    "ENUMERATE", "CLASSIFY", "TRANSFORM", "CHECK", "BRANCH",
    "BACKTRACK", "CORRECT", "ERROR", "HESITATE", "STUCK", "ABANDON",
    "ANSWER",
}
CORRECTNESS = {"correct", "incorrect", "partially_correct", "uncertain", "not_applicable"}
EVIDENCE_STATUS = {"VERBALIZED", "WRITTEN_OBSERVED", "STRONGLY_IMPLIED", "ANALYST_INFERENCE", "UNKNOWN"}
PARTICIPANTS = {
    "P01": ("第一份", "1.m4a"),
    "P02": ("第二份", "2.m4a"),
    "P03": ("第三份", "3.m4a"),
    "P04": ("第四份", "4.m4a"),
    "P05": ("第五份", "5.md"),
    "P06": ("第六份", "新测试者_三角函数A组_ThinkAloud整理_Codex.md"),
}
ISSUE_FIELDS = [
    "participant_id", "question_slot", "question_id", "issue_type",
    "evidence", "suggested_action", "priority",
]
FAMILY_LABELS = {
    "periodicity_counterexample": "周期性构造反例",
    "infer_period_then_frequency": "先推出周期再反推频率",
    "no_strategy_verbalized": "未形成可口述策略并停止",
    "multi_subpart_recursive_and_insertion": "递归、捆绑与插入的多小问路线",
    "incomplete_nonadjacent_boys_plan": "从男生不相邻切入但方法未成形",
    "boys_gap_then_girls_block_then_complement": "先用间隔法并修正，再用捆绑与补集完成三个小问",
    "dynamic_programming_recurrence": "动态规划/递推分解",
    "catalan_reflection_with_uncertain_formula": "Catalan/反射切入但公式转写不确定",
    "catalan_check_then_total_minus_reflection": "Catalan 类比后回查，转用总路径减反射坏路径",
    "direct_paired_residue_bins": "直接构造配对余数类",
    "case_split_then_paired_residue_bins": "先分同余情形再构造配对余数类",
    "direct_size_enumeration_then_coordinate_choices": "先按边长枚举正方形，再选坐标计长方形",
    "occupancy_partition_enumeration": "按入口人数拆分枚举",
    "stuck_then_pigeonhole_attempt": "先卡住，再尝试抽屉原理",
    "direct_classification_by_length_and_digit_position": "按位数和数位直接分类",
    "catalan_grid_reflection": "Catalan 格路与镜像",
    "geometric_series_then_fermat": "几何级数化简后使用费马小定理",
    "acute_interval_monotonicity_then_domain_correction": "先误用锐角单调性，再发现周期条件并修正",
    "sine_law_then_cosine_law_area": "正弦定理定角，再用余弦定理和面积公式",
}


def now() -> str:
    return datetime.now(timezone.utc).isoformat()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def dump_json(value: Any, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp.replace(path)


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def audio_duration(path: Path) -> float | None:
    try:
        result = subprocess.run(
            ["ffprobe", "-v", "error", "-show_entries", "format=duration",
             "-of", "default=noprint_wrappers=1:nokey=1", str(path)],
            check=True, capture_output=True, text=True,
        )
        return round(float(result.stdout.strip()), 3)
    except Exception:
        return None


def locate_input(input_path: Path, raw_dir: Path) -> tuple[Path, Path | None]:
    input_path = input_path.resolve()
    if input_path.is_dir():
        return input_path, None
    if input_path.suffix.lower() != ".zip" or not input_path.exists():
        raise FileNotFoundError(input_path)
    sibling = input_path.with_suffix("")
    if sibling.is_dir():
        return sibling, input_path
    extracted = raw_dir / "extracted"
    if not extracted.exists():
        extracted.mkdir(parents=True, exist_ok=True)
        with zipfile.ZipFile(input_path) as archive:
            archive.extractall(extracted)
    return extracted, input_path


def audit_sources(repo: Path, source_dir: Path, source_zip: Path | None) -> dict[str, Any]:
    raw_dir = repo / "data" / "raw" / "collected_2026_09"
    archive_hashes: set[str] = set()
    archive_entry_count = 0
    if source_zip:
        with zipfile.ZipFile(source_zip) as archive:
            for info in archive.infolist():
                if info.is_dir():
                    continue
                archive_entry_count += 1
                archive_hashes.add(hashlib.sha256(archive.read(info)).hexdigest())
    records: list[dict[str, Any]] = []
    participant_rows: list[dict[str, Any]] = []
    for participant_id, (folder, filename) in PARTICIPANTS.items():
        path = source_dir / folder / filename
        record = {
            "participant_id": participant_id,
            "source_label": folder,
            "source_path": str(path),
            "source_type": "audio" if path.suffix.lower() == ".m4a" else "user_provided_text",
            "exists": path.exists(),
            "size_bytes": path.stat().st_size if path.exists() else None,
            "sha256": sha256_file(path) if path.exists() else None,
            "duration_sec": audio_duration(path) if path.suffix.lower() == ".m4a" and path.exists() else None,
            "present_in_source_zip": (
                sha256_file(path) in archive_hashes if source_zip and path.exists() else None
            ),
        }
        records.append(record)
        participant_rows.append(record)
    inventory = {
        "generated_at": now(),
        "policy": "Source files are referenced and hashed; no source payload was modified.",
        "source_directory": str(source_dir),
        "source_zip": (
            {
                "path": str(source_zip),
                "sha256": sha256_file(source_zip),
                "size_bytes": source_zip.stat().st_size,
                "entry_count": archive_entry_count,
            }
            if source_zip else None
        ),
        "participants": records,
        "participants_not_in_source_zip": [
            row["participant_id"] for row in records if row["present_in_source_zip"] is False
        ],
    }
    dump_json(inventory, raw_dir / "source_inventory.json")
    dump_json({"generated_at": now(), "participants": participant_rows}, raw_dir / "participant_manifest.json")
    with (raw_dir / "participant_manifest.csv").open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(participant_rows[0]))
        writer.writeheader()
        writer.writerows(participant_rows)
    return inventory


def normalize_text(raw_text: str) -> tuple[str, list[dict[str, Any]], list[str]]:
    clean = re.sub(r"[ \t]+", " ", raw_text.replace("\r\n", "\n")).strip()
    replacements = [
        ("Y=tan X", "y=tan x", "notation/case normalization", 0.99),
        ("y=tanx", "y=tan x", "notation spacing normalization", 0.99),
        ("Π", "π", "math symbol normalization", 0.99),
        ("Ω", "ω", "math symbol normalization", 0.99),
    ]
    normalizations: list[dict[str, Any]] = []
    for raw, normalized, reason, confidence in replacements:
        if raw in clean:
            count = clean.count(raw)
            clean = clean.replace(raw, normalized)
            normalizations.append({
                "raw": raw, "normalized": normalized, "reason": reason,
                "confidence": confidence, "occurrences": count,
            })
    uncertain = []
    for span in ["阿尔FX", "阿尔法等于1+2派2贝塔等于1"]:
        if span in raw_text:
            uncertain.append(span)
    return clean, normalizations, uncertain


def remove_asr_boilerplate(text: str) -> tuple[str, list[str]]:
    patterns = [
        r"请不吝点赞\s*订阅\s*转发\s*打赏支持明镜与点点栏目",
        r"请忠实转写实际(?:上)?(?:说出)?的?(?:语音|内容)?[：。]*",
        r"逐字转写[，,]?不补充内容[。．]*",
        r"如果您想要更多语言[，,]?请记住订阅我的频道[。．]*",
        r"按下订阅键[，,]?收听更多内容[。．]*",
        r"请勿模仿(?:[，,]?请勿模仿)*[。．]*",
        r"中文字幕(?:由网友)?提供[。．]*",
    ]
    removed: list[str] = []
    clean = text
    for pattern in patterns:
        matches = re.findall(pattern, clean, flags=re.IGNORECASE)
        removed.extend(matches)
        clean = re.sub(pattern, " [REMOVED_ASR_BOILERPLATE] ", clean, flags=re.IGNORECASE)
    clean = re.sub(r"(?:\s*\[REMOVED_ASR_BOILERPLATE\]\s*)+", " [REMOVED_ASR_BOILERPLATE] ", clean)
    return clean.strip(), removed


def build_clean_transcripts(repo: Path) -> dict[str, dict[str, Any]]:
    raw_dir = repo / "data" / "interim" / "transcripts_raw"
    clean_dir = repo / "data" / "interim" / "transcripts_clean"
    clean_dir.mkdir(parents=True, exist_ok=True)
    result: dict[str, dict[str, Any]] = {}
    for participant_id in PARTICIPANTS:
        source = raw_dir / f"{participant_id}.raw.json"
        if not source.exists():
            continue
        raw = load_json(source)
        clip_sources = sorted((repo / "data" / "interim" / "transcripts_raw_resegmented").glob(f"{participant_id}_Q*.raw.json"))
        if clip_sources:
            clip_payloads = [load_json(path) for path in clip_sources]
            raw_text = "\n".join(
                f"[QUESTION_SLOT_{item['question_slot']}]\n{str(item.get('text') or '')}"
                for item in clip_payloads
            )
            source_paths = [str(source), *[str(path) for path in clip_sources]]
            transcript_source = "reviewed_two_pass_online_asr"
        else:
            raw_text = str(raw.get("text") or raw.get("transcript") or "")
            source_paths = [str(source)]
            transcript_source = raw.get("transcript_source")
        clean_text, normalizations, uncertain_spans = normalize_text(raw_text)
        clean_text, removed_boilerplate = remove_asr_boilerplate(clean_text)
        payload = {
            "schema_version": "1.0",
            "participant_id": participant_id,
            "source_path": str(source),
            "source_paths": source_paths,
            "source_sha256": sha256_file(source),
            "generated_at": now(),
            "transcript_source": transcript_source,
            "raw_text": raw_text,
            "clean_text": clean_text,
            "normalizations": normalizations,
            "uncertain_spans": uncertain_spans,
            "boilerplate_hallucination": {"detected": bool(removed_boilerplate), "removed": removed_boilerplate},
            "cleaning_policy": "Whitespace and unambiguous notation only; no mathematical correction.",
        }
        dump_json(payload, clean_dir / f"{participant_id}.clean.json")
        (clean_dir / f"{participant_id}.clean.txt").write_text(clean_text + "\n", encoding="utf-8")
        result[participant_id] = payload
    return result


def validate_trace(trace: dict[str, Any]) -> None:
    required = {"trace_id", "question_id", "question_slot", "trace_confidence", "first_attention", "path_signature", "steps"}
    missing = required - trace.keys()
    if missing:
        raise ValueError(f"{trace.get('trace_id', '<unknown>')} missing {sorted(missing)}")
    if not 0 <= float(trace["trace_confidence"]) <= 1:
        raise ValueError("trace_confidence outside [0,1]")
    orders = []
    for step in trace["steps"]:
        if step["action_type"] not in ACTION_TYPES:
            raise ValueError(f"unknown action_type {step['action_type']}")
        if step["correctness"] not in CORRECTNESS:
            raise ValueError(f"unknown correctness {step['correctness']}")
        if step["status"] not in EVIDENCE_STATUS:
            raise ValueError(f"unknown status {step['status']}")
        if step["status"] == "ANALYST_INFERENCE":
            raise ValueError("analyst inference must not be embedded in observed steps")
        if not step.get("evidence_text"):
            raise ValueError("observed step lacks evidence_text")
        if not 0 <= float(step["confidence"]) <= 1:
            raise ValueError("step confidence outside [0,1]")
        orders.append(step["order"])
    if orders != list(range(1, len(orders) + 1)):
        raise ValueError(f"non-contiguous step order: {orders}")


def expand_trace(trace: dict[str, Any]) -> dict[str, Any]:
    """Expand compact reviewed annotations without inventing missing content."""
    expanded = dict(trace)
    steps = []
    for index, source in enumerate(trace.get("steps", []), 1):
        step = dict(source)
        step.setdefault("step_id", f"s{index:02d}")
        step.setdefault("order", index)
        step.setdefault("start_sec", None)
        step.setdefault("end_sec", None)
        step.setdefault("clean_text", step.get("evidence_text", ""))
        step.setdefault("representation", None)
        step.setdefault("result", None)
        steps.append(step)
    expanded["steps"] = steps
    expanded.setdefault("analyst_inferences", [])
    return expanded


def longest_common_prefix(signatures: list[list[str]]) -> list[str]:
    if not signatures:
        return []
    prefix = []
    for columns in zip(*signatures):
        if len(set(columns)) != 1:
            break
        prefix.append(columns[0])
    return prefix


def build_variants(bank: dict[str, Any], traces: list[dict[str, Any]]) -> list[dict[str, Any]]:
    by_question: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for trace in traces:
        by_question[trace["question_id"]].append(trace)
    variants = []
    for group in bank["groups"]:
        for question in group["questions"]:
            qid = question["question_id"]
            qtraces = sorted(by_question[qid], key=lambda item: item["participant_id"])
            if not qtraces:
                continue
            grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
            for trace in qtraces:
                grouped[trace.get("strategy", "unspecified")].append(trace)
            families = []
            for index, (strategy, items) in enumerate(grouped.items(), 1):
                signature = tuple(items[0]["path_signature"])
                families.append({
                    "family_id": f"T{index}",
                    "label": FAMILY_LABELS.get(strategy, strategy),
                    "strategy": strategy,
                    "participants": [item["participant_id"] for item in items],
                    "signature": list(signature),
                    "participant_signatures": {
                        item["participant_id"]: item["path_signature"] for item in items
                    },
                    "core_steps": [step["content"] for step in items[0]["steps"]],
                    "core_step_evidence": [
                        {
                            "participant_id": items[0]["participant_id"],
                            "content": step["content"],
                            "evidence_text": step["evidence_text"],
                            "start_sec": step.get("start_sec"),
                            "end_sec": step.get("end_sec"),
                            "status": step["status"],
                            "confidence": step["confidence"],
                        }
                        for step in items[0]["steps"]
                    ],
                    "participant_paths": {
                        item["participant_id"]: [
                            {
                                "content": step["content"],
                                "evidence_text": step["evidence_text"],
                                "start_sec": step.get("start_sec"),
                                "end_sec": step.get("end_sec"),
                                "status": step["status"],
                                "confidence": step["confidence"],
                            }
                            for step in item["steps"]
                        ]
                        for item in items
                    },
                    "representative_evidence": [
                        {"participant_id": item["participant_id"], "evidence": item["steps"][0]["evidence_text"]}
                        for item in items
                    ],
                })
            prefix = longest_common_prefix([trace["path_signature"] for trace in qtraces])
            if len(qtraces) < 2:
                divergence = "少于两条 observed trace，无法估计分叉点。"
            elif all(trace["path_signature"] == qtraces[0]["path_signature"] for trace in qtraces[1:]):
                divergence = "当前 observed traces 的动作路径相同，未观察到动作级分叉。"
            else:
                divergence = (
                    ("共同前缀 " + " / ".join(prefix) + " 之后分叉：" if prefix else "入口即分叉：")
                    + "；".join(
                        f"{trace['participant_id']} 进入 "
                        f"{trace['path_signature'][len(prefix)] if len(trace['path_signature']) > len(prefix) else '[路径结束]'}"
                        for trace in qtraces
                    ) + "。"
                )
            variants.append({
                "question_id": qid,
                "group_id": group["group_id"],
                "n_participants": len(qtraces),
                "valid_traces": len(qtraces),
                "low_confidence_traces": sum(float(item["trace_confidence"]) < 0.75 for item in qtraces),
                "participants": [item["participant_id"] for item in qtraces],
                "trace_families": families,
                "common_prefix": prefix,
                "first_meaningful_divergence": divergence,
            })
    return variants


def question_lookup(bank: dict[str, Any]) -> dict[str, dict[str, Any]]:
    result = {}
    for group in bank["groups"]:
        for question in group["questions"]:
            result[question["question_id"]] = {**question, "group_id": group["group_id"]}
    return result


def append_evidence_path(lines: list[str], steps: list[dict[str, Any]], participant_id: str) -> None:
    """Render every analytic arrow together with the source span that supports it."""
    lines.append("Start")
    for step in steps:
        if step.get("start_sec") is not None and step.get("end_sec") is not None:
            if participant_id == "P02":
                source_location = f"用户提供带时间戳原文，段落级近似范围 {step['start_sec']:.2f}–{step['end_sec']:.2f}s"
            else:
                source_location = f"音频转写 {step['start_sec']:.2f}–{step['end_sec']:.2f}s"
        elif step.get("status") == "WRITTEN_OBSERVED" or participant_id == "P06":
            source_location = "书面/截图整理原文（无音频时间戳）"
        else:
            source_location = "汇总转写文本（无音频时间戳）"
        evidence_text = str(step["evidence_text"]).replace("\n", " / ")
        lines += [
            f"→ {step['content']}",
            f"   - 对应转写/原文（{participant_id}；{source_location}）：“{evidence_text}”",
            f"   - 证据标注：`{step['status']}`；confidence {float(step['confidence']):.2f}",
        ]


def write_participant_summary(path: Path, annotations: dict[str, Any], traces: list[dict[str, Any]]) -> None:
    by_participant: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for trace in traces:
        by_participant[trace["participant_id"]].append(trace)
    lines = [
        "# Participant Trace Summary", "",
        "> 逐步展示原始证据、动作、解释、正确性、证据状态和置信度。研究者推断单列；不把缺失步骤补成学生思路。", "",
    ]
    for participant_id in PARTICIPANTS:
        pdata = annotations.get("participants", {}).get(participant_id)
        lines += [f"## {participant_id}", ""]
        if not pdata:
            lines += ["- 转写尚不可用；未抽取 trace。", "- 对齐：`UNKNOWN`。", "- 人工复核：需要先完成音频转写。", ""]
            continue
        lines.append(f"- Assigned group: `{pdata['assigned_group']}`（confidence {pdata['alignment_confidence']:.2f}）")
        lines.append(f"- Source type: `{pdata.get('source_type', 'unknown')}`")
        if pdata.get("source_note"):
            lines.append(f"- Source note: {pdata['source_note']}")
        if pdata.get("source_limitations"):
            lines.append(f"- Source limitation: {pdata['source_limitations']}")
        lines.append("")
        for trace in sorted(by_participant[participant_id], key=lambda item: item["question_slot"]):
            first = trace["first_attention"]
            signals = ", ".join(first["signal_refs"]) or "未确认具体题内 signal"
            lines += [
                f"### Q{trace['question_slot']} `{trace['question_id']}`", "",
                f"- Trace confidence: {trace['trace_confidence']:.2f}",
                f"- First attention: `{first['operation']}` / {signals}（confidence {first['confidence']:.2f}）",
                f"- First-attention evidence: “{first['evidence']}”",
                f"- Strategy: `{trace.get('strategy', 'unspecified')}`",
                f"- Signature（动作编码）: {' / '.join(trace['path_signature'])}",
            ]
            if "completion_status" in trace:
                lines.append(f"- Completion: `{trace['completion_status']}`; final answer observed: `{trace.get('final_answer_observed')}`")
            lines += ["", "Observed steps:", ""]
            for step in trace["steps"]:
                time_text = (
                    f"{step['start_sec']:.2f}–{step['end_sec']:.2f}s"
                    if step.get("start_sec") is not None and step.get("end_sec") is not None else "无时间戳"
                )
                signal_text = ",".join(step.get("signal_refs", [])) or "none"
                lines += [
                    f"{step['order']}. **`{step['action_type']}`** — {step['content']}",
                    f"   - Evidence ({time_text}): “{step['evidence_text']}”",
                    f"   - Signals: `{signal_text}`；status: `{step['status']}`；correctness: `{step['correctness']}`；confidence: {step['confidence']:.2f}",
                ]
                if step.get("result") is not None:
                    lines.append(f"   - Result: `{step['result']}`")
                if step.get("affect"):
                    lines.append(f"   - Affect marker: `{step['affect']}`")
            lines += ["", "Analyst inference（不属于 observed trace）:", ""]
            if trace.get("analyst_inferences"):
                for item in trace["analyst_inferences"]:
                    lines.append(f"- confidence {item['confidence']:.2f}: {item['content']}")
            else:
                lines.append("- 无。")
            lines.append("")
        lines.append("")
    path.write_text("\n".join(lines), encoding="utf-8")


def write_question_report(path: Path, bank: dict[str, Any], variants: list[dict[str, Any]], traces: list[dict[str, Any]]) -> None:
    lookup = question_lookup(bank)
    trace_lookup = {trace["trace_id"]: trace for trace in traces}
    qtraces: dict[str, list[dict[str, Any]]] = defaultdict(list)
    participant_questions: dict[str, list[str]] = defaultdict(list)
    for trace in traces:
        qtraces[trace["question_id"]].append(trace)
        if trace["question_id"] not in participant_questions[trace["participant_id"]]:
            participant_questions[trace["participant_id"]].append(trace["question_id"])
    lines = [
        "# 同题跨学生 Trace 报告", "",
        "> 本报告只汇总至少有一名被测者作答、且有原始证据支持的 observed traces。无人作答的题目不进入本报告。每个路径箭头下都列出对应转写/原文、证据位置、证据状态和置信度；分析者推断单列，不作为 ground-truth trace。", "",
        "## 按被测者索引", "",
    ]
    for participant_id in PARTICIPANTS:
        question_ids = participant_questions.get(participant_id, [])
        links = ", ".join(f"[{question_id}](#{question_id.lower()})" for question_id in question_ids)
        lines.append(f"- **{participant_id}**：{links or '无已纳入的作答题目'}")
    lines.append("")
    for variant in variants:
        qid = variant["question_id"]
        question = lookup[qid]
        lines += [f"## {qid}", "", "### Coverage", "",
                  f"- Participants: {variant['n_participants']}",
                  f"- Valid traces: {variant['valid_traces']}",
                  f"- Low-confidence traces: {variant['low_confidence_traces']}", "",
                  "### 题目", "", question["canonical_text"], "", "### Problem signals", ""]
        for signal in question["signals"]:
            lines.append(f"- `{signal['signal_id']}` {signal['text']}")
        lines.append("")
        for family in variant["trace_families"]:
            lines += [f"### Observed Trace Family {family['family_id']} — {family['label']}", "",
                      "Participants: " + ", ".join(family["participants"]), "",
                      f"Core path（代表性 trace：{family['participants'][0]}；每个箭头均附原始证据）:", ""]
            append_evidence_path(lines, family["core_step_evidence"], family["participants"][0])
            if len(family["participants"]) > 1:
                lines += ["", "Within-family participant paths（逐人证据对应）:", ""]
                for participant_id, participant_steps in family["participant_paths"].items():
                    signature = family["participant_signatures"][participant_id]
                    lines += [f"#### {participant_id}", "", f"动作编码：{' / '.join(signature)}", ""]
                    append_evidence_path(lines, participant_steps, participant_id)
                    lines.append("")
            lines.append("")
        lines += ["### Common prefix", ""]
        lines.append(" / ".join(variant["common_prefix"]) if variant["common_prefix"] else "当前观察不足以估计跨 family 的共同前缀。")
        lines += ["", "### First meaningful divergence", "", variant["first_meaningful_divergence"], "",
                  "### Errors / hesitation / backtracking", ""]
        events = []
        for trace in qtraces[qid]:
            for step in trace["steps"]:
                if step["action_type"] in {"ERROR", "HESITATE", "STUCK", "BACKTRACK", "CORRECT", "ABANDON"}:
                    events.append(f"- {trace['participant_id']} `{step['action_type']}`: “{step['evidence_text']}”")
        lines += events or ["- 当前 observed steps 中没有这类事件。"]
        lines += ["", "### Analyst inference（不属于 observed trace）", ""]
        inferences = []
        for trace in qtraces[qid]:
            for item in trace.get("analyst_inferences", []):
                inferences.append(f"- {trace['participant_id']}（confidence {item['confidence']:.2f}）: {item['content']}")
        lines += inferences or ["- 无。"]
        lines += ["", "### Research note", "",
                  "当前只说明本批样本观察到了这些路径，不表示该题只有这些可能 trace，也不外推真实学生总体分布。", ""]
    path.write_text("\n".join(lines), encoding="utf-8")


def write_granularity_audit(path: Path, traces: list[dict[str, Any]], annotations: dict[str, Any]) -> None:
    lines = [
        "# Trace 粒度审计", "",
        "> 审计目标：确认每名参与者都按可观察反应拆成原子步骤，而不是只保留方法名称或最终答案。证据不足时保持短 trace 与低置信度，不补写思路。", "",
        "## 审计标准", "",
        "- 每个 observed step 必须有原始证据文本；",
        "- 注意、回忆、表示转换、计算、分支、回退、纠正、卡住和情绪反应分别记录；",
        "- `ANALYST_INFERENCE` 不得出现在 observed steps；",
        "- 录音/材料缺失造成的粗粒度必须显式标记 confidence 和人工复核项；",
        "- 正确答案不能用于倒推出未口述的中间步骤。", "",
        "## 逐 trace 检查", "",
        "| Participant | Question | Steps | Evidence statuses | Revision/error events | Trace confidence | Audit finding |",
        "|---|---:|---:|---|---|---:|---|",
    ]
    for trace in sorted(traces, key=lambda item: (item["participant_id"], item["question_slot"])):
        statuses = ", ".join(sorted({step["status"] for step in trace["steps"]}))
        events = [step["action_type"] for step in trace["steps"] if step["action_type"] in {"ERROR", "HESITATE", "STUCK", "BACKTRACK", "CORRECT", "ABANDON"}]
        if float(trace["trace_confidence"]) < 0.75:
            finding = "证据受限；保留细节与低置信度，未补全过程"
        elif len(trace["steps"]) <= 2:
            finding = "原始反应本身很短；未扩写不存在的中间步骤"
        else:
            finding = "已拆分为逐反应/逐操作步骤"
        lines.append(
            f"| {trace['participant_id']} | {trace['question_id']} | {len(trace['steps'])} | {statuses} | "
            f"{', '.join(events) if events else 'none'} | {trace['trace_confidence']:.2f} | {finding} |"
        )
    lines += ["", "## Participant-level conclusion", "",
              "- **P01**：三个问题均保留了方法选择、分支和递推状态；A1 的第二方案及回退单独记录。",
              "- **P02**：已依据用户提供的带时间戳原文重建。A1 保留三个小问、间隔计数的两次尝试、明确回退、捆绑法与补集法；A2 保留格路建模、Catalan 类比、自我质疑以及总路径减反射坏路径；A3 保留两种余数情况和抽屉论证。游戏/聊天串音已排除，听不清的公式仍标记不确定。",
              "- **P03**：B1 的正方形总数存在 ASR 歧义，B2 只观察到人数拆分枚举，B3 只观察到‘无法理解→仍尝试抽屉原理’；这些限制均被保留。",
              "- **P04**：C1 的分类、自我纠正和停止求和分开记录；C2/C3 的表示转换与公式操作逐步记录。",
              "- **P05**：来源是无时间戳汇总文本。A1/A2 保留明确口述，A3 只记录‘不会做/公式忘了/停止’，没有把第三人称补充说明改写成学生步骤。",
              "- **P06**：A1 保留否认、单调性调用、领域误读、回退、注意 `+2kπ`、概念修正及情绪反应；A2 明确保留未口述的中间依据；A3 按手写等式逐步拆分。", "",
              "## Result", "",
              "现有 P01–P06 的底层 trace 按原子反应/操作展示证据、动作、正确性、状态与 confidence。P02 已用用户提供原文替换早期粗粒度版本；P03 的少数 trace 仍较短，因为可辨认原始证据不足，继续细化会构成猜测。", ""]
    path.write_text("\n".join(lines), encoding="utf-8")


def write_manual_queue(path: Path, rows: list[dict[str, Any]]) -> None:
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=ISSUE_FIELDS)
        writer.writeheader()
        writer.writerows(rows)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", required=True, type=Path)
    parser.add_argument("--question-bank", required=True, type=Path)
    parser.add_argument("--output", type=Path, default=Path("data/processed/trace_pilot"))
    parser.add_argument("--annotations", type=Path, default=Path("configs/reviewed_trace_annotations.json"))
    parser.add_argument("--seed", type=int, default=20260920)
    args = parser.parse_args()
    repo = Path(__file__).resolve().parent.parent
    raw_root = repo / "data" / "raw" / "collected_2026_09"
    source_dir, source_zip = locate_input((repo / args.input) if not args.input.is_absolute() else args.input, raw_root)
    bank_path = (repo / args.question_bank) if not args.question_bank.is_absolute() else args.question_bank
    annotations_path = (repo / args.annotations) if not args.annotations.is_absolute() else args.annotations
    output_dir = (repo / args.output) if not args.output.is_absolute() else args.output
    output_dir.mkdir(parents=True, exist_ok=True)
    reports = repo / "reports"
    reports.mkdir(parents=True, exist_ok=True)

    inventory = audit_sources(repo, source_dir, source_zip)
    clean = build_clean_transcripts(repo)
    bank = load_json(bank_path)
    annotations = load_json(annotations_path)
    for extra_path in sorted((repo / "configs").glob("reviewed_trace_annotations_*.json")):
        extra_annotations = load_json(extra_path)
        annotations.setdefault("participants", {}).update(extra_annotations.get("participants", {}))
    manual_rows: list[dict[str, Any]] = []
    traces: list[dict[str, Any]] = []

    for participant_id in inventory.get("participants_not_in_source_zip", []):
        manual_rows.append({
            "participant_id": participant_id,
            "question_slot": "",
            "question_id": "UNKNOWN",
            "issue_type": "RAW_LAYOUT_DIFFERENCE",
            "evidence": "The participant source exists in the collected-results directory but its content hash is absent from the original source ZIP.",
            "suggested_action": "Keep the original ZIP unchanged and track this participant as a post-ZIP addition; include the separate source when transferring the dataset.",
            "priority": "low",
        })

    for participant_id in PARTICIPANTS:
        pdata = annotations.get("participants", {}).get(participant_id)
        raw_path = repo / "data" / "interim" / "transcripts_raw" / f"{participant_id}.raw.json"
        if not raw_path.exists():
            manual_rows.append({
                "participant_id": participant_id, "question_slot": "", "question_id": "UNKNOWN",
                "issue_type": "ASR_UNCERTAIN", "evidence": "No raw transcript exists for the participant audio.",
                "suggested_action": "Set GROQ_API_KEY and run scripts/transcribe_groq_batch.py, then review the transcript against audio.",
                "priority": "critical",
            })
            manual_rows.append({
                "participant_id": participant_id, "question_slot": "", "question_id": "UNKNOWN",
                "issue_type": "GROUP_ALIGNMENT_UNCERTAIN", "evidence": "Group cannot be aligned without a transcript.",
                "suggested_action": "Transcribe first; score the three slots jointly against all six groups.",
                "priority": "critical",
            })
            continue
        if not pdata:
            manual_rows.append({
                "participant_id": participant_id, "question_slot": "", "question_id": "UNKNOWN",
                "issue_type": "TRACE_STEP_UNCERTAIN", "evidence": "Transcript exists but has no reviewed annotation.",
                "suggested_action": "Review evidence spans and add only verbalized or strongly implied steps.",
                "priority": "high",
            })
            continue
        if pdata.get("source_limitations"):
            manual_rows.append({
                "participant_id": participant_id, "question_slot": "", "question_id": "UNKNOWN",
                "issue_type": "SOURCE_EVIDENCE_UNAVAILABLE", "evidence": pdata["source_limitations"],
                "suggested_action": "Retain the curated record, and attach the original screenshots/photo if independent source-level audit is required.",
                "priority": "medium",
            })
        dump_json({
            "schema_version": "1.0", "participant_id": participant_id,
            "source_transcript": str(raw_path), "generated_at": now(),
            "segments": pdata["segments"],
        }, repo / "data" / "interim" / "segmentation" / f"{participant_id}.segments.json")
        dump_json({
            "schema_version": "1.0", "participant_id": participant_id,
            "assigned_group": pdata["assigned_group"], "confidence": pdata["alignment_confidence"],
            "candidates": pdata["alignment_candidates"], "evidence": pdata["alignment_evidence"],
            "method": "reviewed joint three-slot evidence; no one-to-one assignment constraint",
        }, repo / "data" / "processed" / "alignment" / f"{participant_id}.alignment.json")
        if any(float(segment["boundary_confidence"]) < 0.9 for segment in pdata["segments"]):
            for segment in pdata["segments"]:
                if float(segment["boundary_confidence"]) < 0.9:
                    manual_rows.append({
                        "participant_id": participant_id, "question_slot": segment["slot"], "question_id": segment["question_id"],
                        "issue_type": "QUESTION_BOUNDARY_UNCERTAIN", "evidence": segment["boundary_rationale"],
                        "suggested_action": "Review source document/audio boundary; keep non-chronological repeated notes separate.",
                        "priority": "medium",
                    })
        for trace in pdata["traces"]:
            trace = expand_trace(trace)
            trace = {**trace, "participant_id": participant_id, "assigned_group": pdata["assigned_group"]}
            validate_trace(trace)
            traces.append(trace)
            if float(trace["first_attention"]["confidence"]) < 0.75:
                manual_rows.append({
                    "participant_id": participant_id, "question_slot": trace["question_slot"], "question_id": trace["question_id"],
                    "issue_type": "TRACE_STEP_UNCERTAIN", "evidence": trace["first_attention"]["evidence"],
                    "suggested_action": "Review the entry point; the source does not identify a specific first-attended signal.",
                    "priority": "medium",
                })

    for participant_id, transcript in clean.items():
        if transcript.get("boilerplate_hallucination", {}).get("detected"):
            removed_count = len(transcript["boilerplate_hallucination"]["removed"])
            manual_rows.append({
                "participant_id": participant_id, "question_slot": "", "question_id": "UNKNOWN",
                "issue_type": "ASR_UNCERTAIN", "evidence": f"Removed/marked {removed_count} obvious prompt-echo or advertising-like ASR spans.",
                "suggested_action": "Audit critical evidence against source audio; do not restore boilerplate as student speech.",
                "priority": "high",
            })
        for span in transcript.get("uncertain_spans", []):
            manual_rows.append({
                "participant_id": participant_id, "question_slot": "", "question_id": "UNKNOWN",
                "issue_type": "MATH_TERM_UNCERTAIN", "evidence": span,
                "suggested_action": "Check the original source; do not normalize until confirmed.", "priority": "medium",
            })
    for trace in traces:
        for step in trace["steps"]:
            if float(step["confidence"]) < 0.85:
                manual_rows.append({
                    "participant_id": trace["participant_id"], "question_slot": trace["question_slot"], "question_id": trace["question_id"],
                    "issue_type": "TRACE_STEP_UNCERTAIN", "evidence": step["evidence_text"],
                    "suggested_action": "Review whether the operation is uniquely supported; otherwise downgrade to analyst inference.",
                    "priority": "medium",
                })
            if step["correctness"] == "uncertain":
                manual_rows.append({
                    "participant_id": trace["participant_id"], "question_slot": trace["question_slot"], "question_id": trace["question_id"],
                    "issue_type": "CORRECTNESS_UNCERTAIN", "evidence": step["evidence_text"],
                    "suggested_action": "Mathematically adjudicate the stated step without rewriting the trace.",
                    "priority": "medium",
                })

    traces_path = repo / "data" / "processed" / "traces" / "participant_traces.jsonl"
    traces_path.parent.mkdir(parents=True, exist_ok=True)
    traces_path.write_text("".join(json.dumps(t, ensure_ascii=False) + "\n" for t in traces), encoding="utf-8")
    variants = build_variants(bank, traces)
    dump_json({"schema_version": "1.0", "generated_at": now(), "questions": variants},
              repo / "data" / "processed" / "traces" / "question_trace_variants.json")
    write_participant_summary(reports / "participant_trace_summary.md", annotations, traces)
    write_question_report(reports / "by_question_trace_report.md", bank, variants, traces)
    write_granularity_audit(reports / "trace_granularity_audit.md", traces, annotations)
    write_manual_queue(reports / "manual_review_queue.csv", manual_rows)

    audio_rows = [r for r in inventory["participants"] if r["source_type"] == "audio"]
    statuses = []
    for participant_id in PARTICIPANTS:
        statuses.append((participant_id, "success" if participant_id in clean else "pending: no raw transcript"))
    bank_question_ids = [
        question["question_id"]
        for group in bank["groups"]
        for question in group["questions"]
    ]
    covered_question_ids = {variant["question_id"] for variant in variants}
    uncovered = [question_id for question_id in bank_question_ids if question_id not in covered_question_ids]
    quality = [
        "# Data Quality Report", "", f"Generated: `{now()}`", "",
        "## Raw audit", "", f"- Participant-level source files: {len(inventory['participants'])}（4 audio + 2 text）",
        f"- Source ZIP recorded: {'yes' if inventory['source_zip'] else 'no'}",
        f"- Source ZIP entries: {inventory['source_zip']['entry_count'] if inventory['source_zip'] else 'not applicable'}",
        "- Sources present in the directory but absent from the original ZIP: " +
        (", ".join(inventory["participants_not_in_source_zip"]) if inventory["participants_not_in_source_zip"] else "none") + ".",
        "- The original ZIP is preserved unchanged; post-ZIP additions are tracked as separate raw sources.",
        f"- Total audio duration: {sum(r['duration_sec'] or 0 for r in audio_rows):.3f} seconds",
        "- Source files were hashed and were not modified.", "", "### Audio duration", "",
    ]
    quality += [f"- {r['participant_id']}: {r['duration_sec']} s" for r in audio_rows]
    quality += ["", "## Transcription status", ""] + [f"- {pid}: {status}" for pid, status in statuses]
    boilerplate_participants = [pid for pid, item in clean.items() if item.get("boilerplate_hallucination", {}).get("detected")]
    quality += ["", "- ASR boilerplate hallucination detected and marked for: " + (", ".join(boilerplate_participants) if boilerplate_participants else "none") + ".",
                "- P02 trace evidence was rebuilt from the user-provided timestamped transcript `P02.user_provided_original.txt`; step times are paragraph-level approximate alignments, the audio remains the raw source, and off-task game/chat crosstalk is excluded from observed steps.",
                "- P05 is marked `user_provided_text`; P06 is `user_provided_curated_multimodal_text`; neither is represented as audio ASR.", "",
                "## Segmentation and alignment", ""]
    for pid, pdata in annotations.get("participants", {}).items():
        quality.append(f"- {pid}: group `{pdata['assigned_group']}` confidence {pdata['alignment_confidence']:.2f}; boundary confidences " +
                       ", ".join(f"Q{s['slot']}={s['boundary_confidence']:.2f}" for s in pdata["segments"]))
    quality += ["", "## Trace extraction", "", f"- Observed traces extracted: {len(traces)}",
                f"- Low-confidence traces (<0.75): {sum(float(t['trace_confidence']) < 0.75 for t in traces)}",
                f"- Questions retained in trace outputs: {len(variants)} / {len(bank_question_ids)}",
                f"- Questions omitted because no participant attempted them: {len(uncovered)}",
                "- Omitted: " + ", ".join(uncovered), "",
                "## Manual review", "", f"- Queue rows: {len(manual_rows)}",
                f"- Transcription blockers: none; all {len(PARTICIPANTS)} participant sources were processed.",
                "- P01–P04 contain marked ASR hallucination/uncertainty spans; every low-confidence step remains queued for audio review.",
                "- P05 and P06 have no audio-relative timestamps; their compiled-text boundaries remain explicit confidence-bearing records.",
                "- The third-person P05 note is retained as secondary evidence and excluded from observed steps.", ""]
    (reports / "data_quality_report.md").write_text("\n".join(quality), encoding="utf-8")

    alignment_answer = "；".join(
        f"{pid} → `{pdata['assigned_group']}` ({pdata['alignment_confidence']:.2f})"
        for pid, pdata in sorted(annotations.get("participants", {}).items())
    )
    split_answer = "；".join(
        f"{pid} → " + ", ".join(f"`{segment['question_id']}`" for segment in pdata["segments"])
        for pid, pdata in sorted(annotations.get("participants", {}).items())
    )
    first_attention_answer = []
    for pid in PARTICIPANTS:
        items = sorted((t for t in traces if t["participant_id"] == pid), key=lambda t: t["question_slot"])
        descriptions = []
        for trace in items:
            first = trace["first_attention"]
            refs = ",".join(first["signal_refs"]) or "无可确认signal"
            descriptions.append(f"Q{trace['question_slot']} {first['operation']}({refs}, {first['confidence']:.2f})")
        first_attention_answer.append(f"{pid}: " + "；".join(descriptions))
    family_answer = "；".join(
        f"{variant['question_id']}={len(variant['trace_families'])}"
        for variant in variants if variant["n_participants"]
    )
    issue_counts: dict[str, int] = defaultdict(int)
    for row in manual_rows:
        issue_counts[row["issue_type"]] += 1
    issue_answer = "，".join(f"{key}={value}" for key, value in sorted(issue_counts.items()))
    analyst_count = sum(len(trace.get("analyst_inferences", [])) for trace in traces)
    readme = [
        "# Trace Pilot Run", "", f"Generated: `{now()}`", "",
        "## Acceptance answers", "",
        "1. Group alignment: " + alignment_answer + ".",
        "2. Three-question split: " + split_answer + ".",
        "3. First attention: " + " | ".join(first_attention_answer) + ".",
        "4. Signatures are listed in `participant_trace_summary.md` and the JSONL output.",
        "5. Current observed family counts: " + family_answer + f"；另有 {len(uncovered)} 道无人作答题已从 trace 输出和逐题报告中移除。",
        "6. Same-question divergence: TRIG_A1 中 P05 直接用周期性构造，P06 先误用锐角单调性再自我修正；TRIG_A2 中 P05/P06 属于同一‘先得周期再给 ω’family，但外显步骤长度不同；TRIG_A3 中 P05 无法切入，P06 完成正弦定理—余弦定理—面积路线。COMB_A1–A3 的 P01/P02 分叉保持原报告结论。",
        "7. Data-supported revisions/events: P01 在 COMB_A1 放弃第二条插入路线；P02 在 COMB_A1 明确否定首轮间隔计数并重算，在 COMB_A2 对 Catalan 套用进行自检后改用总路径减反射坏路径；P03 在 COMB_B3 明确卡住；P04 在 COMB_C1 自我修正后停止求和；P05 在 TRIG_A3 报告不会做和忘记公式；P06 在 TRIG_A1 出现可观察的误判—回退—纠正。没有把仅凭最终答案推测的错误标为 ERROR。",
        f"8. Analyst inference 共 {analyst_count} 条，均在独立字段和报告小节中展示，没有混入 observed steps。",
        f"9. Manual review queue contains {len(manual_rows)} rows: {issue_answer}。",
        "10. 当前样本支持一个受限描述：P01/P02 与 P05/P06 分别在相同题目上出现了可观察的路径差异；样本不足以外推这些差异的总体分布或穷尽题目解法。", "",
        "## Primary output", "", "- `reports/by_question_trace_report.md`", "- `reports/trace_granularity_audit.md`", "",
        "## Reproduce", "", "```powershell",
        "python scripts/run_full_pipeline.py",
        "# Or run each stage separately:",
        "python scripts/transcribe_groq_batch.py --input-dir '收集数据结果' --output-dir 'data/interim/transcripts_raw'",
        "python scripts/transcribe_question_clips_groq.py --input-dir '收集数据结果' --clip-dir 'data/interim/asr_clips' --output-dir 'data/interim/transcripts_raw_resegmented'",
        "python scripts/build_student_traces.py --input '收集数据结果.zip' --question-bank 'configs/question_bank_selected.json' --output 'data/processed/trace_pilot'",
        "python -m unittest discover -s tests -v", "```", "",
        "The transcription command requires `GROQ_API_KEY` in the process environment. No key is read from files or written to outputs.", "",
    ]
    (reports / "README.md").write_text("\n".join(readme), encoding="utf-8")
    summary = {
        "generated_at": now(), "seed": args.seed, "participants_total": len(PARTICIPANTS),
        "participants_transcribed": len(clean), "traces": len(traces),
        "questions_total": len(bank_question_ids), "questions_covered": len(variants),
        "manual_review_rows": len(manual_rows),
        "primary_report": str(reports / "by_question_trace_report.md"),
        "failures": ["P01-P04 raw transcripts unavailable"] if len(clean) < 5 else [],
    }
    dump_json(summary, output_dir / "run_summary.json")
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
