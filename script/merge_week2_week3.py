#!/usr/bin/env python3
from __future__ import annotations

import json
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path


def load_jsonl(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def common_prefix(paths: list[list[str]]) -> list[str]:
    if not paths:
        return []
    out: list[str] = []
    for values in zip(*paths):
        if len(set(values)) != 1:
            break
        out.append(values[0])
    return out


def build_variants(traces: list[dict]) -> list[dict]:
    by_question: dict[str, list[dict]] = defaultdict(list)
    for trace in traces:
        by_question[trace["question_id"]].append(trace)

    variants = []
    for question_id in sorted(by_question):
        items = sorted(by_question[question_id], key=lambda x: x["participant_id"])
        by_strategy: dict[str, list[dict]] = defaultdict(list)
        for item in items:
            by_strategy[item.get("strategy") or "unknown"].append(item)

        families = []
        for i, (strategy, family) in enumerate(by_strategy.items(), 1):
            families.append({
                "family_id": f"T{i}",
                "label": strategy.replace("_", " "),
                "strategy": strategy,
                "participants": [x["participant_id"] for x in family],
                "participant_signatures": {x["participant_id"]: x.get("path_signature", []) for x in family},
                "trace_ids": [x["trace_id"] for x in family],
            })

        variants.append({
            "question_id": question_id,
            "group_id": items[0].get("assigned_group"),
            "n_participants": len({x["participant_id"] for x in items}),
            "valid_traces": len(items),
            "low_confidence_traces": sum(float(x.get("trace_confidence", 1)) < 0.75 for x in items),
            "participants": sorted({x["participant_id"] for x in items}),
            "trace_families": families,
            "common_prefix": common_prefix([x.get("path_signature", []) for x in items]),
        })
    return variants


def main() -> int:
    repo = Path(__file__).resolve().parent.parent
    week2_path = repo / "data/processed/traces/participant_traces.jsonl"
    week3_path = repo / "data/exports/week3_combinatorics/participant_traces_combinatorics.jsonl"
    output = repo / "data/combined"
    output.mkdir(parents=True, exist_ok=True)

    week2 = load_jsonl(week2_path)
    week3 = load_jsonl(week3_path)
    traces = week2 + week3
    ids = [x["trace_id"] for x in traces]
    if len(ids) != len(set(ids)):
        raise ValueError("duplicate trace_id across week2/week3")
    traces.sort(key=lambda x: (x["participant_id"], x["question_id"]))

    (output / "participant_traces.jsonl").write_text(
        "".join(json.dumps(x, ensure_ascii=False) + "\n" for x in traces), encoding="utf-8"
    )
    (output / "question_trace_variants.json").write_text(
        json.dumps({
            "schema_version": "1.1",
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "source": "week2 + week3 canonical merge",
            "questions": build_variants(traces),
        }, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    week2_ids = {x["trace_id"] for x in week2}
    index = [{
        "trace_id": x["trace_id"],
        "participant_id": x["participant_id"],
        "question_id": x["question_id"],
        "assigned_group": x.get("assigned_group"),
        "source_period": "week2" if x["trace_id"] in week2_ids else "week3",
        "source_type": x.get("source_type"),
        "source_relative_path": x.get("source_relative_path"),
        "session_id": x.get("session_id"),
        "trace_confidence": x.get("trace_confidence"),
    } for x in traces]
    (output / "trace_index.json").write_text(
        json.dumps(index, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    manifest = {
        "schema_version": "1.0",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "sources": {
            "week2": "data/processed/traces/participant_traces.jsonl",
            "week3": "data/exports/week3_combinatorics/participant_traces_combinatorics.jsonl",
        },
        "counts": {
            "traces": len(traces),
            "week2_traces": len(week2),
            "week3_traces": len(week3),
            "participants": len({x["participant_id"] for x in traces}),
            "questions": len({x["question_id"] for x in traces}),
            "observed_steps": sum(len(x.get("steps", [])) for x in traces),
        },
        "participants": sorted({x["participant_id"] for x in traces}),
        "questions": sorted({x["question_id"] for x in traces}),
        "note": "P05 and P06 appear in both periods on different question domains; trace_id remains unique.",
    }
    (output / "dataset_manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps(manifest["counts"], ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
