from __future__ import annotations

from typing import Any

OPERATION_MAP = {
    "ATTEND": "ATTEND",
    "RECALL": "RECALL",
    "REPRESENT": "REPRESENT",
    "TRANSFORM": "REPRESENT",
    "PLAN": "PLAN",
    "CLASSIFY": "REASON",
    "ENUMERATE": "REASON",
    "DERIVE": "REASON",
    "CALCULATE": "COMPUTE",
    "CHECK": "CHECK",
    "ANSWER": "RESPOND",
}
CONTROL_MAP = {"BRANCH": "BRANCH", "BACKTRACK": "BACKTRACK", "ABANDON": "ABANDON"}
STATE_MAP = {"HESITATE": "HESITATING", "STUCK": "STUCK"}

OPERATION_VALUES = ["ATTEND", "RECALL", "REPRESENT", "PLAN", "REASON", "COMPUTE", "CHECK", "RESPOND"]
CONTROL_VALUES = ["CONTINUE", "BRANCH", "BACKTRACK", "ABANDON"]
COGNITIVE_STATE_VALUES = ["NORMAL", "HESITATING", "STUCK"]


def _label_status(observation_status: str | None) -> str:
    return "INFERRED" if observation_status == "STRONGLY_IMPLIED" else "OBSERVED"


def axis(value: str | None, legacy: str | None, confidence: float | None, observation_status: str | None) -> dict[str, Any]:
    if value is None:
        return {"value": None, "subtype": None, "status": "UNKNOWN", "confidence": None}
    return {
        "value": value,
        "subtype": legacy if legacy != value else None,
        "status": _label_status(observation_status),
        "confidence": confidence if isinstance(confidence, (int, float)) else None,
    }


def migrate_first_attention(item: dict[str, Any] | None) -> dict[str, Any] | None:
    if not item:
        return None
    legacy = item.get("operation")
    confidence = item.get("confidence")
    return {
        "signal_refs": item.get("signal_refs", []),
        "operation": axis(OPERATION_MAP.get(legacy), legacy, confidence, "VERBALIZED"),
        "control": axis(CONTROL_MAP.get(legacy), legacy, confidence, "VERBALIZED"),
        "cognitive_state": axis(STATE_MAP.get(legacy), legacy, confidence, "VERBALIZED"),
        "evidence": {"text": item.get("evidence"), "confidence": confidence},
        "legacy_label": legacy,
    }


def migrate_step(step: dict[str, Any]) -> dict[str, Any]:
    legacy = step.get("action_type")
    correctness = step.get("correctness", "uncertain")
    if legacy == "ERROR" and correctness == "not_applicable":
        correctness = "incorrect"
    return {
        "step_id": step.get("step_id"),
        "order": step.get("order"),
        "content": step.get("content"),
        "operation": axis(OPERATION_MAP.get(legacy), legacy, step.get("confidence"), step.get("status")),
        "control": axis(CONTROL_MAP.get(legacy), legacy, step.get("confidence"), step.get("status")),
        "cognitive_state": axis(STATE_MAP.get(legacy), legacy, step.get("confidence"), step.get("status")),
        "correctness": {"value": correctness, "status": "ANNOTATED", "confidence": None},
        "representation": step.get("representation"),
        "result": step.get("result"),
        "revision": {
            "type": "CORRECTION",
            "target_step_id": None,
            "target_status": "UNKNOWN",
            "confidence": step.get("confidence"),
        } if legacy == "CORRECT" else None,
        "affect": step.get("affect"),
        "evidence": {
            "text": step.get("evidence_text"),
            "clean_text": step.get("clean_text", step.get("evidence_text")),
            "signal_refs": step.get("signal_refs", []),
            "start_sec": step.get("start_sec"),
            "end_sec": step.get("end_sec"),
            "observation_status": step.get("status"),
            "confidence": step.get("confidence"),
            "visual_evidence": step.get("visual_evidence"),
        },
        "legacy_action_type": legacy,
    }


def migrate_trace(trace: dict[str, Any]) -> dict[str, Any]:
    keep = [
        "trace_id", "participant_id", "question_id", "question_slot", "assigned_group",
        "trace_confidence", "strategy", "completion_status", "final_answer_observed",
        "analyst_inferences", "source_relative_path", "source_modalities", "session_id",
        "source_type", "video_review",
    ]
    out = {key: trace[key] for key in keep if key in trace}
    out["first_attention"] = migrate_first_attention(trace.get("first_attention"))
    out["legacy_path_signature"] = trace.get("path_signature", [])
    out["steps"] = [migrate_step(step) for step in trace.get("steps", [])]
    out["operation_path"] = [
        step["operation"]["value"] for step in out["steps"]
        if step["operation"]["value"] is not None
    ]
    return out


def migrate_prediction_input(value: dict[str, Any]) -> dict[str, Any]:
    result = dict(value)
    result["schema_version"] = "2.0"
    result["trace_schema"] = "multi_axis_student_trace_v2"
    observations = []
    for raw in value.get("a_group_observations", []):
        item = dict(raw)
        item["first_attention"] = migrate_first_attention(raw.get("first_attention"))
        item["legacy_path_signature"] = raw.get("path_signature", [])
        item.pop("path_signature", None)
        item["observed_steps"] = [migrate_step(step) for step in raw.get("observed_steps", [])]
        item["operation_path"] = [
            step["operation"]["value"] for step in item["observed_steps"]
            if step["operation"]["value"] is not None
        ]
        observations.append(item)
    result["a_group_observations"] = observations
    return result


def wrap_traces(traces: list[dict[str, Any]]) -> dict[str, Any]:
    step_count = sum(len(trace.get("steps", [])) for trace in traces)
    return {
        "schema_version": "2.0",
        "schema_name": "multi_axis_student_trace",
        "annotation_policy": {
            "principle": "Only label a dimension when the existing evidence supports it; UNKNOWN must not be interpreted as NORMAL or CONTINUE.",
            "operation_values": OPERATION_VALUES,
            "control_values": CONTROL_VALUES,
            "cognitive_state_values": COGNITIVE_STATE_VALUES,
            "label_status_values": ["OBSERVED", "INFERRED", "UNKNOWN"],
            "correctness_values": ["correct", "partially_correct", "incorrect", "uncertain", "not_applicable"],
            "migration_note": "This migration never infers NORMAL or CONTINUE from the absence of an old label.",
        },
        "counts": {"traces": len(traces), "steps": step_count},
        "traces": traces,
    }
