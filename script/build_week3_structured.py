#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import re
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ACTION_TYPES = {
    "ATTEND", "RECALL", "REPRESENT", "PLAN", "BRANCH", "CLASSIFY",
    "ENUMERATE", "DERIVE", "CALCULATE", "CHECK", "HESITATE", "STUCK",
    "BACKTRACK", "CORRECT", "ABANDON", "ANSWER",
}
CORRECTNESS = {"correct", "partially_correct", "uncertain", "not_applicable"}
MACHINE_SOURCE = "groq_whisper_large_v3_audio_only_machine_structured_pending_human_review"


def step(
    start: float,
    end: float | None,
    evidence: str,
    signals: list[str],
    action: str,
    content: str,
    correctness: str,
    confidence: float,
    token: str,
    *,
    representation: str | None = None,
    result: str | None = None,
) -> dict[str, Any]:
    return {
        "start_sec": start,
        "end_sec": end,
        "evidence_text": evidence,
        "signal_refs": signals,
        "action_type": action,
        "content": content,
        "correctness": correctness,
        "status": "VERBALIZED",
        "confidence": confidence,
        "representation": representation,
        "result": result,
        "_token": token,
    }


def inference(content: str, confidence: float) -> dict[str, Any]:
    return {"content": content, "status": "ANALYST_INFERENCE", "confidence": confidence}


def make_trace(
    participant_id: str,
    question_id: str,
    slot: int,
    confidence: float,
    first_attention: dict[str, Any],
    strategy: str,
    steps: list[dict[str, Any]],
    source_relative_path: str,
    session_id: str,
    source_type: str,
    analyst_inferences: list[dict[str, Any]] | None = None,
    completion_status: str | None = None,
) -> dict[str, Any]:
    output_steps = []
    signature = []
    for index, raw in enumerate(steps, 1):
        item = dict(raw)
        signature.append(item.pop("_token"))
        item["step_id"] = f"s{index:02d}"
        item["order"] = index
        item["clean_text"] = item["evidence_text"]
        output_steps.append(item)
    assigned_group = question_id[:-1]
    trace = {
        "trace_id": f"{participant_id}_{question_id}",
        "question_id": question_id,
        "question_slot": slot,
        "trace_confidence": confidence,
        "first_attention": first_attention,
        "strategy": strategy,
        "path_signature": signature,
        "steps": output_steps,
        "analyst_inferences": analyst_inferences or [],
        "participant_id": participant_id,
        "assigned_group": assigned_group,
        "source_relative_path": source_relative_path,
        "source_modalities": ["timestamped_transcript"] if participant_id == "P05" else ["audio"],
        "session_id": session_id,
        "source_type": source_type,
    }
    if completion_status:
        trace["completion_status"] = completion_status
    return trace


def normalize(value: str) -> str:
    return re.sub(r"[\W_]+", "", value, flags=re.UNICODE).lower()


def load_source_text(repo: Path, trace: dict[str, Any]) -> str:
    if trace["participant_id"] == "P05":
        return (repo / trace["source_relative_path"]).read_text(encoding="utf-8")
    transcript = repo / "data" / "interim" / "audio_transcripts" / trace["participant_id"] / "sessions" / trace["session_id"] / "transcript.txt"
    return transcript.read_text(encoding="utf-8")


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def longest_common_prefix(paths: list[list[str]]) -> list[str]:
    if not paths:
        return []
    result = []
    for values in zip(*paths):
        if len(set(values)) != 1:
            break
        result.append(values[0])
    return result


def build_variants(traces: list[dict[str, Any]], question_groups: list[dict[str, Any]]) -> list[dict[str, Any]]:
    by_question: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for trace in traces:
        by_question[trace["question_id"]].append(trace)
    group_lookup = {
        q["question_id"]: group["group_id"]
        for group in question_groups
        for q in group["questions"]
    }
    variants = []
    for question_id in sorted(by_question):
        items = sorted(by_question[question_id], key=lambda item: item["participant_id"])
        strategy_groups: dict[str, list[dict[str, Any]]] = defaultdict(list)
        for item in items:
            strategy_groups[item["strategy"]].append(item)
        families = []
        for family_index, (strategy, family_items) in enumerate(strategy_groups.items(), 1):
            representative = family_items[0]
            families.append({
                "family_id": f"T{family_index}",
                "label": strategy.replace("_", " "),
                "strategy": strategy,
                "participants": [item["participant_id"] for item in family_items],
                "signature": representative["path_signature"],
                "participant_signatures": {
                    item["participant_id"]: item["path_signature"] for item in family_items
                },
                "core_steps": [item["content"] for item in representative["steps"]],
                "core_step_evidence": [
                    {
                        "participant_id": representative["participant_id"],
                        "content": item["content"],
                        "evidence_text": item["evidence_text"],
                        "start_sec": item["start_sec"],
                        "end_sec": item["end_sec"],
                        "status": item["status"],
                        "confidence": item["confidence"],
                    }
                    for item in representative["steps"]
                ],
                "participant_paths": {
                    trace["participant_id"]: [
                        {
                            "content": item["content"],
                            "evidence_text": item["evidence_text"],
                            "start_sec": item["start_sec"],
                            "end_sec": item["end_sec"],
                            "status": item["status"],
                            "confidence": item["confidence"],
                        }
                        for item in trace["steps"]
                    ]
                    for trace in family_items
                },
                "representative_evidence": [
                    {"participant_id": item["participant_id"], "evidence": item["steps"][0]["evidence_text"]}
                    for item in family_items
                ],
            })
        prefix = longest_common_prefix([item["path_signature"] for item in items])
        if len(items) < 2:
            divergence = "少于两条 observed trace，无法估计分叉点。"
        elif all(item["path_signature"] == items[0]["path_signature"] for item in items[1:]):
            divergence = "当前 observed traces 的动作路径相同，未观察到动作级分叉。"
        else:
            lead = "共同前缀 " + " / ".join(prefix) + " 之后分叉：" if prefix else "入口即分叉："
            branches = []
            for item in items:
                next_token = item["path_signature"][len(prefix)] if len(item["path_signature"]) > len(prefix) else "[路径结束]"
                branches.append(f"{item['participant_id']} 进入 {next_token}")
            divergence = lead + "；".join(branches) + "。"
        variants.append({
            "question_id": question_id,
            "group_id": group_lookup[question_id],
            "n_participants": len(items),
            "valid_traces": len(items),
            "low_confidence_traces": sum(float(item["trace_confidence"]) < 0.75 for item in items),
            "participants": [item["participant_id"] for item in items],
            "trace_families": families,
            "common_prefix": prefix,
            "first_meaningful_divergence": divergence,
        })
    return variants


def build_traces() -> list[dict[str, Any]]:
    traces: list[dict[str, Any]] = []
    p05a = "data/raw/student_materials/1/A组/原文.md"
    p05b = "data/raw/student_materials/1/B组/原文.md"
    p05type = "user_provided_timestamped_transcript"
    machine = MACHINE_SOURCE

    traces.append(make_trace("P05", "COMB_A1", 1, 0.96,
        {"signal_refs": ["C1"], "operation": "ATTEND", "evidence": "任何两个男生都不相邻", "confidence": 0.99},
        "girls_first_gap_insertion_then_complement", [
            step(12, 58, "任何两个男生都不相邻", ["C1"], "ATTEND", "先关注男生互不相邻。", "correct", 0.99, "ATTEND(C1)"),
            step(58, 143, "女生看作一共有这样的 N 个点", ["C1"], "REPRESENT", "先排列女生，并把女生之间及两端表示为 n+1 个空位。", "correct", 0.98, "REPRESENT(n+1-gaps)", representation="gap_insertion"),
            step(58, 143, "要在 N 加一个空格里面去放 M 个男生", ["C1"], "CALCULATE", "从 n+1 个空位中选 m 个，再排列 m 名男生。", "correct", 0.94, "CALCULATE(select-gaps-and-permute-boys)"),
            step(143, 174, "这里公式可能不记得了", ["C1"], "HESITATE", "知道间隔法结构，但不确定排列组合记号。", "not_applicable", 0.99, "HESITATE(formula-notation)"),
            step(143, 200, "好，然后是第二题。N 个女生形成一个整整体。", ["C2"], "ATTEND", "转入女生形成整体的小问。", "correct", 0.99, "ATTEND(C2)"),
            step(200, 311, "那我理解就是一个 pm 加一的全排列！女生之间也可以。全排列一下。", ["C2"], "CALCULATE", "把女生整体与男生排列，并乘女生内部排列。", "correct", 0.91, "CALCULATE(bundle-girls)"),
            step(200, 311, "指定男生 a 和指定女生 B 不相邻，我们可以用补集的思想", ["C3"], "PLAN", "对指定 A、B 不相邻采用补集。", "correct", 0.99, "PLAN(complement)"),
            step(200, 311, "相邻有两种可能，是 ab，一个是 ba。我们把他们看作一个整体", ["C3"], "REPRESENT", "把相邻的 AB 或 BA 捆绑为一个整体。", "correct", 0.98, "REPRESENT(adjacent-pair)"),
            step(311, 364, "最终的答案就是 M 加 N 的。阶乘减去两倍的 M 加 N 减一的阶乘。", ["C3"], "ANSWER", "用总排列减去两种相邻次序的排列。", "correct", 0.99, "ANSWER(total-minus-adjacent)", result="(m+n)!-2(m+n-1)!")
        ], p05a, "P05__1__A_original", p05type, completion_status="completed"))

    traces.append(make_trace("P05", "COMB_A2", 2, 0.94,
        {"signal_refs": ["S1", "S2", "S3"], "operation": "REPRESENT", "evidence": "平面点01？从这里出发", "confidence": 0.98},
        "grid_model_then_hint_and_abandon", [
            step(364, 411, "平面点01？从这里出发", ["S1"], "REPRESENT", "从 (0,1) 出发画格路图。", "correct", 0.98, "REPRESENT(lattice-path)", representation="lattice_path"),
            step(411, 554, "X 轴走。M.", ["S2"], "CALCULATE", "识别横向走 m 步、纵向走 n-1 步。", "correct", 0.96, "CALCULATE(step-counts)"),
            step(554, 619, "现在相当于就是 y0大于等于 x0", ["S3"], "DERIVE", "把不接触对角线改写为前缀步数约束。", "correct", 0.90, "DERIVE(prefix-constraint)"),
            step(799, 866, "我记得好像是有个模型，但是我有点忘记了", ["G"], "RECALL", "想起存在标准格路模型，但无法回忆。", "not_applicable", 0.99, "RECALL(model-forgotten)"),
            step(866, 907, "实在是想不起来了，我们看一下附录。", ["G"], "STUCK", "在无法继续后查看附录提示。", "not_applicable", 0.99, "STUCK(read-hint)"),
            step(907, 1019, "需要和另一类更容易数的路径。建立11对应的关系。这说的有点抽象。", ["G"], "ATTEND", "读到一一对应提示，但认为提示抽象。", "not_applicable", 0.99, "ATTEND(hint-bijection)"),
            step(1019, 1091, "我们可以把它分为三种情况", ["S3"], "BRANCH", "按路径始终在上方、接触、越过三种情况分类。", "partially_correct", 0.87, "BRANCH(three-path-cases)"),
            step(1091, 1139, "其他的用补集的思想就可以解决", ["G"], "PLAN", "尝试计算坏路径再用补集。", "correct", 0.92, "PLAN(complement-illegal-paths)"),
            step(1139, 1216, "我们现在要在这个里面插入 x0", ["G"], "PLAN", "尝试把横向步插入纵向步序列，但未形成完整计数。", "uncertain", 0.82, "PLAN(gap-insertion-attempt)"),
            step(1216, 1216, "这道题实在想不出来，我们过吧", ["G"], "ABANDON", "明确停止该题。", "not_applicable", 0.99, "ABANDON")
        ], p05a, "P05__1__A_original", p05type,
        [inference("附录内容参与了后续思路，因此该 trace 不是无提示独立解答。", 1.0)], "abandoned_after_hint"))

    traces.append(make_trace("P05", "COMB_A3", 3, 0.93,
        {"signal_refs": ["S1", "S3"], "operation": "ATTEND", "evidence": "七和10是这两个数字会比较特殊", "confidence": 0.98},
        "residue_algebra_attempts_then_pigeonhole_bins", [
            step(1216, 1290, "七和10是这两个数字会比较特殊", ["S1", "S3"], "ATTEND", "先注意数字7与模10结构。", "not_applicable", 0.98, "ATTEND(7-and-10)"),
            step(1290, 1420, "设 yi 等于10加 xi", ["S3"], "REPRESENT", "尝试用除以10后的余数参数表示各整数。", "partially_correct", 0.80, "REPRESENT(residue-parameters)", representation="mod_10"),
            step(1420, 1601, "理论上这里已经能够枚举了", ["S2", "S3"], "ENUMERATE", "尝试在余数坐标图中枚举和、差。", "uncertain", 0.78, "ENUMERATE(sum-difference-grid)"),
            step(1735, 1820, "我感觉好像有点算复杂了。再重新思考一下这个问题。", ["G"], "BACKTRACK", "因代数枚举复杂而重新开始。", "not_applicable", 0.99, "BACKTRACK(first-algebra-attempt)"),
            step(1820, 1900, "把这两个式子加1加就是2xi 是10的倍数", ["S2", "S3"], "DERIVE", "把和、差条件相加，尝试推出余数为5的倍数。", "partially_correct", 0.81, "DERIVE(add-equations)"),
            step(1890, 1984, "感觉不太对，再看一下", ["G"], "CHECK", "检查并否定刚才的推导。", "not_applicable", 0.98, "CHECK(reject-derivation)"),
            step(2161, 2323, "我们直接用这个直接算这个数", ["G"], "CALCULATE", "尝试直接计数和或差为10倍数的余数对。", "uncertain", 0.76, "CALCULATE(residue-pairs-attempt)"),
            step(2483, 2580, "现在思路有点乱，我们重新捋一下，我们直接用反证法", ["G"], "BACKTRACK", "再次回退并改用反证法。", "not_applicable", 0.99, "BACKTRACK(to-contradiction)"),
            step(2525, 2645, "他们这个余数肯定都是不相等的", ["S2", "S3"], "CLASSIFY", "反设下先推出七个余数两两不同。", "correct", 0.93, "CLASSIFY(distinct-residues)"),
            step(2702, None, "六组里面却要选7个，根据鸽巢原理", ["G"], "REPRESENT", "把个位数按相等或和为10的关系分成六组。", "correct", 0.97, "REPRESENT(six-residue-bins)", representation="pigeonhole_bins"),
            step(2702, None, "势必会有两个，那么就不成立，所以这道题就得证。", ["G"], "ANSWER", "用七个余数进入六组的鸽巢原理完成反证。", "correct", 0.97, "ANSWER(pigeonhole-contradiction)")
        ], p05a, "P05__1__A_original", p05type, completion_status="completed_after_multiple_backtracks"))

    traces.append(make_trace("P05", "COMB_B1", 1, 0.97,
        {"signal_refs": ["S1", "G1"], "operation": "REPRESENT", "evidence": "我们先画个图", "confidence": 0.99},
        "choose_coordinate_pairs_then_enumerate_square_sizes", [
            step(4, 114, "我们先画个图", ["S1"], "REPRESENT", "画出10乘8的格点区域。", "correct", 0.99, "REPRESENT(grid)"),
            step(4, 114, "在10个点里面取两个点，然后再乘以这里，一共是8个点。然后也在里面取两个点", ["G1"], "CALCULATE", "分别选两个横坐标和两个纵坐标来确定轴平行长方形。", "correct", 0.98, "CALCULATE(C10,2-times-C8,2)", result="C(10,2)·C(8,2)"),
            step(114, 267, "边长为 a", ["G2"], "CLASSIFY", "按正方形边长 a=1到7分类。", "correct", 0.98, "CLASSIFY(square-side-length)"),
            step(147, 267, "A 等于一的时候", ["G2"], "ENUMERATE", "逐个边长计算正方形可放置位置。", "correct", 0.92, "ENUMERATE(square-placements)"),
            step(267, 275, "暂时想不到就死算吧", ["G2"], "ANSWER", "决定保留逐项求和，没有口述最终和。", "partially_correct", 0.96, "ANSWER(leave-as-sum)")
        ], p05b, "P05__1__B_original", p05type, completion_status="partial_numeric_answer"))

    traces.append(make_trace("P05", "COMB_B2", 2, 0.92,
        {"signal_refs": ["S1", "S2", "S3"], "operation": "HESITATE", "evidence": "我怎么感觉这道题我理解有点问题。", "confidence": 0.99},
        "multiple_recurrence_attempts_then_grid_recurrence", [
            step(307, 366, "我怎么感觉这道题我理解有点问题。", ["S1", "S2", "S3"], "HESITATE", "首先质疑自己是否理解进站方案。", "not_applicable", 0.99, "HESITATE(problem-meaning)"),
            step(610, 676, "我们假设6个门都用上", ["S1", "S2"], "PLAN", "先讨论六个入口都使用的情况。", "partially_correct", 0.94, "PLAN(all-six-used)"),
            step(621, 676, "从9个人里面选出6个人，这6个人是一个全排列", ["S2", "S3"], "CALCULATE", "先给每个门放一人，再考虑剩余三人。", "partially_correct", 0.87, "CALCULATE(seed-each-door)"),
            step(676, 769, "这方式好像不是很好", ["G"], "BACKTRACK", "认为按使用门数分类过于复杂，放弃该路线。", "not_applicable", 0.99, "BACKTRACK(all-six-used)"),
            step(849, 1013, "可以这样设，我们看看能不能用通项的方式解决", ["G"], "PLAN", "定义人数与门数参数，尝试建立递推。", "correct", 0.96, "PLAN(recurrence-Snm)"),
            step(1013, 1257, "相当于多出来了这一个人，这个人可以去6个门中的任意一个门", ["S3"], "DERIVE", "尝试按新增一人递推，但遗漏插入现有队列的多个位置。", "partially_correct", 0.84, "DERIVE(add-one-person)"),
            step(1455, 1623, "这个做法好像不太", ["G"], "CHECK", "发现递推会导向6的9次方，判断方法有问题。", "not_applicable", 0.98, "CHECK(recurrence-problem)"),
            step(1623, 1770, "我们重新来看", ["G"], "BACKTRACK", "重新构造按门数变化的递推。", "not_applicable", 0.99, "BACKTRACK(rebuild-recurrence)"),
            step(1785, 1903, "其实是格子，类似，一一直要走到这个点", ["G"], "REPRESENT", "把递推关系联想到格路和组合数。", "uncertain", 0.82, "REPRESENT(grid-recurrence)"),
            step(1903, 1957, "因为他这里。九的全排列，所以是 p99再乘以 C 的15。", ["G"], "ANSWER", "给出9!乘某个组合数的结果，但组合数上下标在原文中不清。", "uncertain", 0.72, "ANSWER(formula-uncertain)", result="[ASR_UNCERTAIN: 9! multiplied by a combination number]")
        ], p05b, "P05__1__B_original", p05type,
        [inference("最后组合数的上下标不能从原文可靠恢复。", 1.0)], "completed_with_uncertain_formula"))

    traces.append(make_trace("P05", "COMB_B3", 3, 0.91,
        {"signal_refs": ["S1", "S2"], "operation": "RECALL", "evidence": "其实跟之前 a3的鸽巢原理还挺像的", "confidence": 0.98},
        "doubling_pairs_pigeonhole_attempt", [
            step(1957, 2082, "其实跟之前 a3的鸽巢原理还挺像的", ["G"], "RECALL", "第一反应是与A3类似的鸽巢原理。", "not_applicable", 0.98, "RECALL(pigeonhole)"),
            step(2082, 2262, "大胆假设一下这个倍数我们就特指二", ["S2"], "PLAN", "先只考虑二倍关系。", "partially_correct", 0.94, "PLAN(doubling-only)"),
            step(2262, 2402, "我们可以用反证法", ["G"], "PLAN", "尝试反证并逐步排除选择1、2。", "partially_correct", 0.90, "PLAN(contradiction)"),
            step(2402, 2474, "这样的组？只能存在？只有多少组？只有 N 减二组。", ["S1", "S2"], "REPRESENT", "把数按 (k,2k) 配对并估计组数，但这些配对可能重叠。", "uncertain", 0.82, "REPRESENT(doubling-pairs)"),
            step(2474, None, "让我再重新思考一下", ["G"], "CHECK", "对组数差距表示担忧并复查。", "not_applicable", 0.98, "CHECK(pair-count)"),
            step(2474, None, "这里一共是 N 组。我们要选 N 加一个数，那么肯定会有一组里面有两个数", ["G"], "ANSWER", "用N+1个数进入N个二倍配对的鸽巢论证作答。", "uncertain", 0.84, "ANSWER(pigeonhole-doubling-pairs)")
        ], p05b, "P05__1__B_original", p05type,
        [inference("原文没有证明 (k,2k) 构成互不重叠的 N 个鸽巢，因此最终论证的正确性需另行数学复核。", 0.98)], "completed_with_logical_gap"))

    # P06: B group, long video-derived audio.
    p06src = "data/raw/student_materials/2/RPReplay_Final1790170222.MP4"
    p06sid = "P06__2__RPReplay_Final1790170222"
    traces.append(make_trace("P06", "COMB_B1", 1, 0.72,
        {"signal_refs": ["G1"], "operation": "REPRESENT", "evidence": "那长方形不就是四个,四个坐标,四个坐标来决定这个长方形吗?", "confidence": 0.91},
        "lower_left_attempt_then_coordinate_choices", [
            step(50, 62, "那长方形不就是四个,四个坐标,四个坐标来决定这个长方形吗?", ["G1"], "REPRESENT", "认为长方形由横纵坐标选择决定。", "correct", 0.91, "REPRESENT(coordinate-choice)"),
            step(62, 99, "你只要确定某个顶点以及长和宽", ["G1"], "PLAN", "先尝试枚举左下角、长和宽。", "correct", 0.88, "PLAN(lower-left-length-width)"),
            step(99, 183, "比如说我规定了,就规定左下角的顶点就行了", ["G1"], "ENUMERATE", "枚举可作左下角的点；中间大量ASR缺失。", "uncertain", 0.60, "ENUMERATE(lower-left-points)"),
            step(339, 346, "那就是756,28乘以45。", ["G1"], "ANSWER", "转而用选择两个横坐标和两个纵坐标，给出28×45=756。", "correct", 0.91, "ANSWER(C8,2-times-C10,2)", result="756"),
            step(349, 393, "然后其中的正方形的数目。", ["G2"], "ATTEND", "转入正方形计数。", "not_applicable", 0.95, "ATTEND(G2)"),
            step(391, 428, "长为1长为2", ["G2"], "CLASSIFY", "按边长分类并尝试找求和规律。", "partially_correct", 0.78, "CLASSIFY(square-side-length)"),
            step(477, 495, "6加5加4加3加2加1。", ["G2"], "CALCULATE", "口述一个递减求和片段，但完整公式无法从ASR恢复。", "uncertain", 0.62, "CALCULATE(square-sum-uncertain)", result="[ASR_UNCERTAIN: square-count summation]")
        ], p06src, p06sid, machine,
        [inference("104–324秒出现大量提示回声和广告式幻觉，未作为 observed steps。", 1.0)], "completed_rectangles_square_formula_uncertain"))

    traces.append(make_trace("P06", "COMB_B2", 2, 0.59,
        {"signal_refs": ["S1", "S2", "S3"], "operation": "HESITATE", "evidence": "进站方案它指的是啥?", "confidence": 0.95},
        "occupancy_composition_attempt_then_stuck", [
            step(535, 547, "进站方案它指的是啥?", ["S3"], "HESITATE", "首先不确定‘进站方案’是否包含进入顺序。", "not_applicable", 0.95, "HESITATE(problem-meaning)"),
            step(577, 594, "那如果我的X,SE加什么什么加X,最后应该是等我9个人进站。", ["S1", "S2"], "REPRESENT", "尝试用各入口人数之和为9表示方案。", "partially_correct", 0.55, "REPRESENT(occupancy-sum)", result="[ASR_UNCERTAIN: occupancy equation]"),
            step(652, 683, "1加6s2加a6s3,1加到a6si", ["G"], "CALCULATE", "尝试按使用入口数写求和式，但符号无法可靠恢复。", "uncertain", 0.48, "CALCULATE(sum-over-used-entrances)", result="[ASR_UNCERTAIN: summation formula]"),
            step(706, 740, "然后我9个怎么分配,对吧?", ["S2", "G"], "STUCK", "回到9个人如何分配的问题，未形成可验证的计数。", "not_applicable", 0.72, "STUCK(distribution)")
        ], p06src, p06sid, machine,
        [inference("最后一步的放弃由持续ASR幻觉和800.6秒题目切换共同支持，未观察到学生明确说‘放弃’。", 0.72)], "no_answer_observed"))

    traces.append(make_trace("P06", "COMB_B3", 3, 0.69,
        {"signal_refs": ["G"], "operation": "PLAN", "evidence": "你就反正呗。没想到反正就不存在倍数。", "confidence": 0.86},
        "contradiction_then_odd_part_pigeonhole", [
            step(809.6, 824.6, "你就反正呗。没想到反正就不存在倍数。", ["G"], "PLAN", "第一反应是反设任意两数不存在倍数关系。", "partially_correct", 0.86, "PLAN(contradiction)"),
            step(920.34, 940, "把所有的写成", ["S2"], "REPRESENT", "开始把1到2n中的数写成2的幂乘另一因子；该段ASR需复核。", "partially_correct", 0.55, "REPRESENT(power-of-two-times-q)"),
            step(946, 973, "1就等于2的0次方乘以1,2就等于2的1次方乘以1,3就等于2的0。", ["S2"], "ENUMERATE", "用1、2、3等例子探索2进赋值分解。", "partially_correct", 0.70, "ENUMERATE(factorization-examples)"),
            step(1066.444, 1088.444, "比如说,2的某个次方,可以次方,乘以一个q。", ["S2"], "CORRECT", "修正为每个数可持续提出2的因子，余下q为奇数。", "correct", 0.79, "CORRECT(odd-part-factorization)"),
            step(1175.889, 1216.333, "2的k字方式是q,q从1到n中便利。", ["S1", "S2"], "CLASSIFY", "按奇数部分q分类，并认为q落在不超过2n的n个奇数中。", "correct", 0.68, "CLASSIFY(odd-part-bins)"),
            step(1216.333, 1228.333, "那有勾勺原理", ["G"], "DERIVE", "调用鸽巢原理得到两个数具有相同奇数部分。", "correct", 0.72, "DERIVE(pigeonhole)"),
            step(1228.333, 1262.493, "必然存在某两个数", ["G"], "ANSWER", "以相同奇数部分的两个数之比为2的幂，推出倍数关系；公式ASR不清。", "correct", 0.63, "ANSWER(same-odd-part)", result="[ASR_UNCERTAIN: ratio of powers of two]")
        ], p06src, p06sid, machine,
        [inference("902–1034秒包含多处 review_required，奇数部分分解需要优先听音复核。", 1.0)], "completed_pending_audio_review"))

    # P07: one long audio containing both A and B groups; highly noisy ASR.
    p07src = "data/raw/student_materials/3/20260923-180329-b45f3662/audio.m4a"
    p07sid = "P07__20260923-180329-b45f3662__audio"
    traces.append(make_trace("P07", "COMB_A1", 1, 0.51,
        {"signal_refs": ["C2"], "operation": "REPRESENT", "evidence": "M 女生形成一个整体,那你把 M 女生看成是一个", "confidence": 0.68},
        "bundle_and_complement_fragments", [
            step(60, 73, "M 女生形成一个整体,那你把 M 女生看成是一个", ["C2"], "REPRESENT", "观察到女生整体小问，并采用捆绑。", "correct", 0.68, "REPRESENT(bundle-girls)"),
            step(65, 84, "M 就是 M 加 1 的阶层,然后再看 M 女生本身是 M 阶层。", ["C2"], "CALCULATE", "尝试写出整体排列乘内部排列；m/n在ASR中混淆。", "uncertain", 0.50, "CALCULATE(bundle-formula-uncertain)", result="[ASR_UNCERTAIN: m/n indices]") ,
            step(114, 126, "M加n的介绍解析,两倍的M加n-e的介绍。对。", ["C3"], "ANSWER", "似乎口述总数减两倍相邻数，但公式严重损坏。", "uncertain", 0.42, "ANSWER(complement-formula-uncertain)", result="[ASR_UNCERTAIN: likely total minus adjacent count]")
        ], p07src, p07sid, machine,
        [inference("A1第一小问未从ASR中恢复；不能据第二周标准路径补写。", 1.0)], "partial_only_subparts_2_3"))

    traces.append(make_trace("P07", "COMB_A2", 2, 0.50,
        {"signal_refs": ["S2"], "operation": "ATTEND", "evidence": "然后到第二步的时候,它就可以往右也可以往上。", "confidence": 0.68},
        "symmetry_attempt_then_total_paths", [
            step(200, 206.12, "然后到第二步的时候,它就可以往右也可以往上。", ["S2"], "ATTEND", "注意每步可向右或向上。", "correct", 0.68, "ATTEND(step-directions)"),
            step(291.86, 316.94, "如果有一种走法是不接触这条直线的对称的话", ["S3"], "PLAN", "尝试用关于直线的对称建立路径对应。", "uncertain", 0.55, "PLAN(symmetry-attempt)"),
            step(317, 338, "恒常要走m个,数值要走n减一个,Cm加n减一个取m。", ["S1", "S2"], "CALCULATE", "计算忽略约束时需走m步向右、n-1步向上。", "correct", 0.69, "CALCULATE(total-paths)", result="C(m+n-1,m)"),
            step(475, 479.28, "我给大家映射了一条合法的录音室。", ["G"], "PLAN", "疑似提到映射合法路径，但ASR语义不可靠。", "uncertain", 0.35, "PLAN(mapping-uncertain)")
        ], p07src, p07sid, machine,
        [inference("A2中338–475秒主要为提示回声，无法确认反射映射是否真正完成。", 1.0)], "incomplete"))

    traces.append(make_trace("P07", "COMB_A3", 3, 0.48,
        {"signal_refs": ["S1"], "operation": "ATTEND", "evidence": "OK,重要的是7个不同的正等数。", "confidence": 0.55},
        "noisy_mod10_pairing_attempt", [
            step(559, 561, "OK,重要的是7个不同的正等数。", ["S1"], "ATTEND", "先关注七个数互不相同。", "not_applicable", 0.55, "ATTEND(seven-distinct)"),
            step(682, 690.88, "模10以下呼应。", ["S3"], "REPRESENT", "转向模10余数。", "partially_correct", 0.45, "REPRESENT(mod10)"),
            step(701.26, 731, "在这五个队作为模10的语书的意义下,那么这七个里面必定有两个位于同一队的。", ["G"], "REPRESENT", "尝试构造余数配对并用鸽巢原理；配对口述严重失真。", "uncertain", 0.38, "REPRESENT(residue-pairs-uncertain)"),
            step(791, 823, "前四组如果任意有有两个是同一组,直接整理。", ["G"], "DERIVE", "按余数组讨论七个数落组情况。", "uncertain", 0.45, "DERIVE(case-pigeonhole)"),
            step(823, 862, "只有两个数可以选了。所以这会就是我们的一次这样的证明了。", ["G"], "ANSWER", "宣告完成证明，但末段ASR不足以还原严格论证。", "uncertain", 0.40, "ANSWER(proof-uncertain)")
        ], p07src, p07sid, machine,
        [inference("余数配对内容必须人工听音，不能据标准六类自动修正。", 1.0)], "claimed_complete_asr_uncertain"))

    traces.append(make_trace("P07", "COMB_B1", 1, 0.62,
        {"signal_refs": ["S1"], "operation": "ATTEND", "evidence": "一共有80个点。", "confidence": 0.86},
        "point_pair_attempt_then_square_side_enumeration", [
            step(892, 899, "一共有80个点。", ["S1"], "ATTEND", "先计算格点总数为80。", "correct", 0.86, "ATTEND(80-points)"),
            step(899, 945.88, "首先,C812是80个点里,认取两个点的各数中,它们要减去。", ["G1"], "CALCULATE", "尝试从点对总数中排除无效点对，再除以对角线重复；组合数ASR不清。", "uncertain", 0.48, "CALCULATE(point-pair-method)", result="[ASR_UNCERTAIN: point-pair formula]"),
            step(964, 983, "正方形就要求选一个左下角的点,然后往外扩展。", ["G2"], "PLAN", "以左下角和边长枚举正方形。", "correct", 0.72, "PLAN(lower-left-and-side)"),
            step(1000, 1016.5, "不能这样学习,这样学习就麻烦了,不这样想。", ["G2"], "BACKTRACK", "认为当前按坐标分类过于麻烦并回退。", "not_applicable", 0.68, "BACKTRACK(coordinate-cases)"),
            step(1030, 1034, "先少一些点试试。", ["G2"], "PLAN", "改为用较小规模寻找规律。", "not_applicable", 0.70, "PLAN(small-cases)"),
            step(1099, 1149.68, "在横向上可以有9个数学生规划,有7种不同的系统。", ["G2"], "ENUMERATE", "按边长逐项口述横纵可放位置；若干乘积被ASR破坏。", "uncertain", 0.50, "ENUMERATE(square-sizes)", result="[ASR_UNCERTAIN: side-length products]")
        ], p07src, p07sid, machine, completion_status="partial"))

    traces.append(make_trace("P07", "COMB_B2", 2, 0.38,
        {"signal_refs": ["S2", "S1"], "operation": "REPRESENT", "evidence": "这九个球变成一样的状态是把九个球放到六个盒子里", "confidence": 0.52},
        "balls_into_boxes_fragment", [
            step(1212.56, 1220.76, "这九个球变成一样的状态是把九个球放到六个盒子里", ["S1", "S2"], "REPRESENT", "把九个人进入六个入口表示成球入盒。", "partially_correct", 0.52, "REPRESENT(balls-into-boxes)")
        ], p07src, p07sid, machine,
        [inference("无法判断学生是否处理了人物不同与同一入口内顺序；不得从球盒表述补出公式。", 1.0)], "no_answer_observed"))

    traces.append(make_trace("P07", "COMB_B3", 3, 0.40,
        {"signal_refs": ["G"], "operation": "PLAN", "evidence": "这个归纳法,第一种情况,n等于1", "confidence": 0.62},
        "induction_then_pairing_fragments", [
            step(1369, 1407, "这个归纳法,第一种情况,n等于1", ["G"], "PLAN", "首先尝试数学归纳法。", "partially_correct", 0.62, "PLAN(induction)"),
            step(1511, 1537, "3.6是一段。", ["S2"], "ENUMERATE", "枚举3与6、4与8、5与10等倍数对。", "partially_correct", 0.55, "ENUMERATE(doubling-pairs)"),
            step(1576, 1585, "把这个课将把n个数分出。", ["G"], "REPRESENT", "似乎尝试把1到2n分组，但ASR无法恢复分组规则。", "uncertain", 0.32, "REPRESENT(n-groups-uncertain)"),
            step(1832, 1845.68, "那么这样不同的Q的几个组数呢,我们这种就怕要算是n组。", ["G"], "CALCULATE", "估计存在n个组，但q的定义听不清。", "uncertain", 0.35, "CALCULATE(n-bins-uncertain)", result="[ASR_UNCERTAIN: definition of q bins]"),
            step(1875.68, 1910.96, "例如,n等于2的时候是1,2,3,4。", ["S1"], "CHECK", "用n=2的小例子检查。", "not_applicable", 0.55, "CHECK(n=2-example)")
        ], p07src, p07sid, machine,
        [inference("B3没有足够语音证据确认学生形成了标准奇数部分分类。", 1.0)], "incomplete"))

    # P08: A group.
    p08src = "data/raw/student_materials/4/873b577486d64746e50992d1b86ac88d.mp4"
    p08sid = "P08__4__873b577486d64746e50992d1b86ac88d"
    traces.append(make_trace("P08", "COMB_A1", 1, 0.57,
        {"signal_refs": ["C1"], "operation": "ATTEND", "evidence": "任何两个男生都不相邻。", "confidence": 0.80},
        "boys_first_internal_gaps_formula_uncertain", [
            step(90, 119, "任何两个男生都不相邻。", ["C1"], "ATTEND", "关注男生互不相邻。", "correct", 0.80, "ATTEND(C1)"),
            step(145, 155.6, "M-1 里面至少每一个位置都要放一个女生进去。", ["C1"], "REPRESENT", "先排男生，并要求m-1个内部间隔各放一名女生。", "correct", 0.70, "REPRESENT(m-1-internal-gaps)"),
            step(215.6, 233.14, "男生的左边就是这个位置和这个位置也是可以插入的。", ["C1"], "ATTEND", "进一步考虑男生序列两端也可插入女生。", "correct", 0.73, "ATTEND(end-gaps)"),
            step(233.14, 237, "所以现在就是c n-m-a。词中有数字,请读。", ["C1"], "CALCULATE", "尝试写选择空位的组合数，但上下标无法恢复。", "uncertain", 0.35, "CALCULATE(combination-uncertain)", result="[ASR_UNCERTAIN: combination indices]"),
            step(295, 322, "试习后,还要对女生进行一个全排列。", ["C1"], "CALCULATE", "补充女生需要全排列，并口述若干乘积因子。", "partially_correct", 0.58, "CALCULATE(permutation-factors-uncertain)", result="[ASR_UNCERTAIN: permutation product]")
        ], p08src, p08sid, machine,
        [inference("A1第二、三小问在ASR中没有可靠内容，未补写。", 1.0)], "partial_only_subpart_1"))

    traces.append(make_trace("P08", "COMB_A2", 2, 0.65,
        {"signal_refs": ["S1", "S2"], "operation": "REPRESENT", "evidence": "0 1 出发。", "confidence": 0.90},
        "case_split_then_hint_and_first_contact_sum", [
            step(477, 494.22, "0 1 出发。", ["S1"], "REPRESENT", "从(0,1)出发并识别每步向右或向上。", "correct", 0.90, "REPRESENT(lattice-path)", representation="lattice_path"),
            step(622, 643.52, "然后那这个分两种情况嘛。", ["S1", "S3"], "BRANCH", "尝试按m=n-1等终点与对角线距离分类。", "uncertain", 0.74, "BRANCH(endpoint-distance)"),
            step(737, 741, "感觉现在就是有点想不下去了。", ["G"], "STUCK", "明确卡住。", "not_applicable", 0.99, "STUCK"),
            step(771, 784.86, "能不能把第一次碰到 x 等于 y 的不合法路径和另一类更容易数的路径建立一一对应关系?", ["G"], "ATTEND", "读取第一次接触边界并建立对应的提示。", "not_applicable", 0.98, "ATTEND(hint-first-contact)"),
            step(801, 825.58, "不关x等于y这个条件。", ["G"], "CALCULATE", "先忽略限制，计算总路径为在m+n-1步中选m步。", "correct", 0.92, "CALCULATE(total-paths)", result="C(m+n-1,m)"),
            step(892, 904, "什么是第一次接触到的这个路径?", ["S3"], "HESITATE", "仍不理解第一次接触路径的对应。", "not_applicable", 0.90, "HESITATE(first-contact-mapping)"),
            step(982, 1020.82, "那么首先从01到AA有多少种可能性呢?", ["G"], "ENUMERATE", "改为按首次接触点(a,a)求和。", "partially_correct", 0.80, "ENUMERATE(first-contact-point-sum)", result="Σ C(2a-1,a)"),
            step(1021.9, 1111, "我感觉这个可能算到这里不就可以了", ["G"], "ANSWER", "把首次接触点组合数求和作为结果，表示不会继续化简。", "uncertain", 0.75, "ANSWER(sum-left-unsimplified)")
        ], p08src, p08sid, machine,
        [inference("771秒后的提示参与了策略变化；该过程不是无提示独立解答。", 1.0)], "completed_with_unsimplified_uncertain_sum"))

    traces.append(make_trace("P08", "COMB_A3", 3, 0.62,
        {"signal_refs": ["S1"], "operation": "ATTEND", "evidence": "感觉可能是要远反正反", "confidence": 0.72},
        "contradiction_then_hint_residue_pairing", [
            step(1161, 1173, "感觉可能是要远反正反", ["G"], "PLAN", "第一反应是尝试反证，并追问为什么必须是7个数。", "partially_correct", 0.72, "PLAN(contradiction)"),
            step(1245.46, 1261.98, "从模10来想,观察两颗整数,这分别意味着它们个位数之间有什么关系。", ["S2", "S3"], "ATTEND", "读取按模10和个位数分类的提示。", "not_applicable", 0.86, "ATTEND(hint-mod10)"),
            step(1261.98, 1281.88, "好,我们考虑它的个位数。", ["S3"], "REPRESENT", "转而考虑七个数的个位数。", "correct", 0.88, "REPRESENT(last-digits)"),
            step(1281.88, 1338, "要么他们的个位数相等", ["S2", "S3"], "DERIVE", "推出所需关系对应个位数相等或互补为10。", "correct", 0.70, "DERIVE(equal-or-complementary)"),
            step(1338, 1358, "鸽巢原理是什么来着?", ["G"], "RECALL", "尝试回忆鸽巢原理及其与余数分组的关系。", "not_applicable", 0.83, "RECALL(pigeonhole)"),
            step(1491, 1502, "比如说这个地方其实就是个4和6是冲突的。", ["S2", "S3"], "REPRESENT", "用4与6说明互补余数冲突，并主张任取7个会出现冲突对。", "partially_correct", 0.72, "REPRESENT(complementary-pairs)"),
            step(1502, 1533.441, "我们可以把它对半", ["G"], "ANSWER", "提出把10个个位数配对后使用鸽巢原理，但结尾被ASR幻觉截断。", "uncertain", 0.58, "ANSWER(pair-and-pigeonhole-incomplete)")
        ], p08src, p08sid, machine,
        [inference("1245秒后由提示引导；1491秒后的最终配对分组需人工听音确认。", 1.0)], "claimed_complete_pending_review"))

    # P09: three separate A-question audios.
    p09type = machine
    traces.append(make_trace("P09", "COMB_A1", 1, 0.68,
        {"signal_refs": ["C1"], "operation": "REPRESENT", "evidence": "男生用方块表示,女生用圆圈表示。", "confidence": 0.86},
        "small_example_then_gap_insertion_and_two_person_insertion", [
            step(40.04, 48.04, "男生用方块表示,女生用圆圈表示。", ["S1", "C1"], "REPRESENT", "用方块和圆圈表示男女生。", "correct", 0.86, "REPRESENT(symbols)"),
            step(48.04, 90.04, "先画一个图,进行一个尝试。", ["C1"], "PLAN", "先取具体m、n画图找规律。", "not_applicable", 0.90, "PLAN(small-example)"),
            step(109.54, 158.32, "四个空都可以,那就是C42,从,不对,A42。", ["C1"], "CHECK", "在n=3、m=2例子中纠结应使用组合还是排列，随后确认男生不同。", "partially_correct", 0.78, "CHECK(C-vs-A)"),
            step(194.32, 224.12, "我先排女生,然后呢,因为男生不能相邻", ["C1"], "PLAN", "识别插空法：先排女生，再把男生放入空位。", "correct", 0.90, "PLAN(gap-insertion)"),
            step(257, 294.5, "女生先进行全排列,就是m的,不是,n的阶层", ["C1"], "CORRECT", "自我修正女生全排列为n!，再尝试写男生插空因子。", "partially_correct", 0.73, "CORRECT(n-factorial)", result="[ASR_UNCERTAIN: remaining gap factor]"),
            step(445, 461, "男生A和女生B不相邻。", ["C3"], "ATTEND", "转入指定A、B不相邻的小问；第二小问未从ASR恢复。", "not_applicable", 0.85, "ATTEND(C3)"),
            step(537, 556.376, "M-N-2它进行全排列。", ["C3"], "PLAN", "尝试先排列其余m+n-2人，再把A、B插入空位。", "uncertain", 0.62, "PLAN(arrange-rest-then-insert)"),
            step(556.376, 584.676, "只要是不相连,它基本上都插空站。", ["C3"], "CALCULATE", "用插空处理A、B不相邻，但最终乘积公式无法可靠恢复。", "uncertain", 0.55, "CALCULATE(two-person-gap-formula)", result="[ASR_UNCERTAIN: A/B insertion formula]")
        ], "data/raw/student_materials/5/A1.m4a", "P09__5__A1", p09type,
        [inference("A1第二小问在ASR中没有可靠语义内容，未补写。", 1.0)], "partial"))

    traces.append(make_trace("P09", "COMB_A2", 2, 0.73,
        {"signal_refs": ["S2", "S3"], "operation": "RECALL", "evidence": "如果要是没有不接触直线X等于Y的这个条件的话", "confidence": 0.82},
        "unconstrained_path_model_then_hint_stuck", [
            step(26.3, 47.64, "如果要是没有不接触直线X等于Y的这个条件的话", ["S2", "S3"], "RECALL", "先想到忽略对角线限制时是典型步序排列。", "correct", 0.82, "RECALL(unconstrained-path-count)"),
            step(47.64, 68.64, "我发现这块多了一个要求,就是不接触直线。", ["S3"], "ATTEND", "识别困难来自不能接触或穿过x=y。", "correct", 0.94, "ATTEND(diagonal-constraint)"),
            step(68.64, 93.64, "Mn 先作为例子,假设 m 等于几,n 等于几", ["S1"], "PLAN", "画网格并尝试具体m、n寻找规律。", "not_applicable", 0.70, "PLAN(small-example)"),
            step(415, 424.6, "其实我有点没有思路了。", ["G"], "STUCK", "明确表示没有思路并决定查看提示。", "not_applicable", 0.99, "STUCK(read-hint)"),
            step(432.44, 443.8, "可以先忽略X等于Y这个限制。", ["G"], "ATTEND", "读取先计算无约束路径的提示。", "not_applicable", 0.95, "ATTEND(hint-ignore-constraint)"),
            step(473.8, 496, "横杠书冠它本身是没有什么要求的嘛", ["G"], "CALCULATE", "尝试写无约束路径组合数，但ASR公式不清。", "partially_correct", 0.56, "CALCULATE(total-paths-uncertain)", result="[ASR_UNCERTAIN: total path combination indices]"),
            step(496, 517, "能不能把第一次碰到和另一类容易数的路径建立一一对应?", ["G"], "HESITATE", "读到首次接触反射提示，但询问其含义。", "not_applicable", 0.93, "HESITATE(first-contact-bijection)"),
            step(517, 550, "什么叫第一次碰到X等于Y的不合法路径和另一类更容易数的路径?", ["G"], "ABANDON", "未观察到建立映射或最终答案。", "not_applicable", 0.88, "ABANDON(no-mapping)")
        ], "data/raw/student_materials/5/A2.m4a", "P09__5__A2", p09type,
        [inference("提示在432秒后直接影响路径，不能把后续视为盲解。", 1.0)], "no_answer_observed"))

    traces.append(make_trace("P09", "COMB_A3", 3, 0.67,
        {"signal_refs": ["S2", "S3"], "operation": "REPRESENT", "evidence": "A-b 模10等于0?", "confidence": 0.62},
        "equation_attempt_then_last_digit_contradiction", [
            step(145, 183, "A-b 模10等于0?", ["S2", "S3"], "REPRESENT", "先把整除条件写成模10同余或10的倍数方程。", "partially_correct", 0.62, "REPRESENT(mod-equations)"),
            step(265, 273, "他那个公式我忘了。我想一想啊。", ["G"], "HESITATE", "忘记所需公式并停顿。", "not_applicable", 0.95, "HESITATE(formula-forgotten)"),
            step(281, 297, "各位数之间有什么关系?哦!", ["S3"], "ATTEND", "转而关注个位数关系。", "correct", 0.87, "ATTEND(last-digit-relation)"),
            step(338, 352, "我知道他们两个是相等或是互补了,然后呢?", ["S2", "S3"], "DERIVE", "识别两数个位相等或互补，但不知道如何继续。", "correct", 0.90, "DERIVE(equal-or-complementary)"),
            step(429, 460, "证明反正法是否有用?", ["G"], "PLAN", "尝试反设任意一对的和、差都不能被10整除。", "partially_correct", 0.72, "PLAN(contradiction)"),
            step(537, 583.3, "任意两个都不能相同,也不能互补。", ["S2", "S3"], "CLASSIFY", "反设下要求七个个位数互异且无互补对。", "correct", 0.66, "CLASSIFY(distinct-noncomplementary-digits)"),
            step(583.3, 601.6, "第二点,既然它都不相同,就必定要选0-9当中的7个不同的末位数。", ["S1", "G"], "DERIVE", "由余数互异推出需选七个不同末位数；之后未观察到鸽巢分组或最终证明。", "partially_correct", 0.58, "DERIVE(distinct-last-digits)")
        ], "data/raw/student_materials/5/A3.m4a", "P09__5__A3", p09type,
        [inference("录音末尾未出现可恢复的六类余数分组，不能补成标准答案。", 1.0)], "incomplete"))

    return traces


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo-root", type=Path, default=Path.cwd())
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    repo = args.repo_root.resolve()
    output = (args.output or (repo / "data" / "exports" / "week3_combinatorics")).resolve()
    output.mkdir(parents=True, exist_ok=True)

    metadata_source = repo / "configs" / "question_metadata_combinatorics.json"
    metadata = json.loads(metadata_source.read_text(encoding="utf-8"))
    traces = build_traces()

    evidence_failures = []
    schema_failures = []
    for trace in traces:
        source_text = normalize(load_source_text(repo, trace))
        previous_start = -1.0
        for index, item in enumerate(trace["steps"], 1):
            if item["action_type"] not in ACTION_TYPES or item["correctness"] not in CORRECTNESS:
                schema_failures.append(f"{trace['trace_id']} step {index}: invalid ontology value")
            if item["start_sec"] < previous_start:
                schema_failures.append(f"{trace['trace_id']} step {index}: nonmonotonic time")
            previous_start = item["start_sec"]
            if normalize(item["evidence_text"]) not in source_text:
                evidence_failures.append({
                    "trace_id": trace["trace_id"], "step_id": item["step_id"],
                    "evidence_text": item["evidence_text"],
                })
        if len(trace["path_signature"]) != len(trace["steps"]):
            schema_failures.append(f"{trace['trace_id']}: signature length mismatch")
        if any(item.get("status") == "ANALYST_INFERENCE" for item in trace["steps"]):
            schema_failures.append(f"{trace['trace_id']}: inference leaked into observed steps")

    variants = build_variants(traces, metadata["groups"])
    annotations: dict[str, Any] = {"schema_version": "1.0", "participants": {}}
    by_participant: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for trace in traces:
        by_participant[trace["participant_id"]].append(trace)
    participant_source_types = {
        "P05": "user_provided_timestamped_transcript",
        "P06": MACHINE_SOURCE, "P07": MACHINE_SOURCE,
        "P08": MACHINE_SOURCE, "P09": MACHINE_SOURCE,
    }
    segment_bounds = {
        "P05": [
            ("COMB_A1", 12, 364, 0.99), ("COMB_A2", 364, 1216, 0.99), ("COMB_A3", 1216, None, 0.99),
            ("COMB_B1", 4, 275, 0.99), ("COMB_B2", 275, 1957, 0.99), ("COMB_B3", 1957, None, 0.99),
        ],
        "P06": [("COMB_B1", 0, 497, 0.98), ("COMB_B2", 497, 800.6, 0.94), ("COMB_B3", 800.6, 1287.777, 0.96)],
        "P07": [("COMB_A1", 0, 200, 0.72), ("COMB_A2", 200, 537, 0.82), ("COMB_A3", 537, 892, 0.86),
                ("COMB_B1", 892, 1208.56, 0.95), ("COMB_B2", 1208.56, 1369, 0.74), ("COMB_B3", 1369, 1994.78, 0.77)],
        "P08": [("COMB_A1", 90, 477, 0.82), ("COMB_A2", 477, 1113, 0.96), ("COMB_A3", 1113, 1585.923, 0.97)],
        "P09": [("COMB_A1", 0, 602.752, 1.0), ("COMB_A2", 0, 550.016, 1.0), ("COMB_A3", 0, 601.6, 1.0)],
    }
    for participant_id, participant_traces in sorted(by_participant.items()):
        groups = sorted({trace["assigned_group"] for trace in participant_traces})
        annotations["participants"][participant_id] = {
            "source_type": participant_source_types[participant_id],
            "assigned_group": "_AND_".join(groups),
            "alignment_confidence": min(value[3] for value in segment_bounds[participant_id]),
            "alignment_evidence": [
                f"{trace['question_id']} aligned from source path and question-specific vocabulary."
                for trace in participant_traces
            ],
            "segments": [
                {
                    "slot": int(question_id[-1]), "question_id": question_id,
                    "start_sec": start, "end_sec": end,
                    "boundary_confidence": confidence,
                    "boundary_rationale": "Filename/folder hint or explicit question transition; see DATA_QUALITY_REPORT.md for uncertain boundaries.",
                    "text": next(trace["strategy"] for trace in participant_traces if trace["question_id"] == question_id),
                }
                for question_id, start, end, confidence in segment_bounds[participant_id]
            ],
            "traces": [
                {key: value for key, value in trace.items() if key not in {"participant_id", "assigned_group"}}
                for trace in sorted(participant_traces, key=lambda value: (value["assigned_group"], value["question_slot"]))
            ],
        }

    trace_path = output / "participant_traces_combinatorics.jsonl"
    trace_path.write_text("".join(json.dumps(item, ensure_ascii=False) + "\n" for item in traces), encoding="utf-8")
    write_json(output / "reviewed_trace_annotations_combinatorics.json", annotations)
    write_json(output / "question_trace_variants_combinatorics.json", {
        "schema_version": "1.0", "generated_at": datetime.now(timezone.utc).isoformat(), "questions": variants,
    })
    write_json(output / "question_metadata_combinatorics.json", metadata)

    prediction_dir = output / "prediction_inputs"
    prediction_dir.mkdir(exist_ok=True)
    prediction_participants = []
    for participant_id in ["P05", "P07", "P08", "P09"]:
        a_traces = sorted(
            (trace for trace in by_participant[participant_id] if trace["assigned_group"] == "COMB_A"),
            key=lambda item: item["question_slot"],
        )
        if not a_traces:
            continue
        prediction_participants.append(participant_id)
        write_json(prediction_dir / f"{participant_id}_from_A.json", {
            "schema_version": "1.0",
            "participant_id": participant_id,
            "input_group": "COMB_A",
            "target_group": "COMB_B",
            "blindness_note": "This file contains no current-participant B transcript, B trace, or B outcome.",
            "a_group_observations": [
                {
                    "question_id": trace["question_id"],
                    "first_attention": trace["first_attention"],
                    "strategy": trace["strategy"],
                    "path_signature": trace["path_signature"],
                    "observed_steps": trace["steps"],
                    "analyst_inferences": trace["analyst_inferences"],
                }
                for trace in a_traces
            ],
        })

    low_conf_steps = [
        (trace["participant_id"], trace["question_id"], item)
        for trace in traces for item in trace["steps"] if float(item["confidence"]) < 0.75
    ]
    formula_review = [
        (trace["participant_id"], trace["question_id"], item)
        for trace in traces for item in trace["steps"]
        if isinstance(item.get("result"), str) and "ASR_UNCERTAIN" in item["result"]
    ]
    priority = sorted(low_conf_steps, key=lambda value: float(value[2]["confidence"]))[:20]
    step_counts = Counter((trace["participant_id"], trace["question_id"]) for trace in traces for _ in trace["steps"])
    report = [
        "# 第三周 Audio-first 数据质量报告", "",
        f"生成时间：`{datetime.now(timezone.utc).isoformat()}`", "",
        "## 范围", "",
        "- P05：仅使用 A组/B组 `原文.md`，未调用 Groq。",
        "- P06/P08：仅使用 MP4 抽取音频后的 Groq 分段转写。",
        "- P07：仅使用 `audio.m4a`；没有读取视频或笔迹来推断认知。",
        "- P09：使用 A1/A2/A3 三段 M4A 的 Groq 分段转写。", "",
        "## 题目与 step 数", "",
        "| Participant | Questions | Steps | Source type |", "|---|---|---:|---|",
    ]
    for participant_id in sorted(by_participant):
        for trace in sorted(by_participant[participant_id], key=lambda value: (value["assigned_group"], value["question_slot"])):
            report.append(f"| {participant_id} | {trace['question_id']} | {len(trace['steps'])} | `{trace['source_type']}` |")
    report += ["", "## 质量统计", "",
        f"- Participants: {len(by_participant)}",
        f"- Traces: {len(traces)}",
        f"- Observed steps: {sum(len(trace['steps']) for trace in traces)}",
        f"- Low-confidence steps (<0.75): {len(low_conf_steps)}",
        f"- Formula spans pending review: {len(formula_review)}",
        f"- Evidence lookup failures: {len(evidence_failures)}",
        f"- Schema/ordering failures: {len(schema_failures)}", "",
        "## 待人工复核公式", "",
    ]
    for participant_id, question_id, item in formula_review:
        report.append(f"- {participant_id} `{question_id}` {item['start_sec']}–{item['end_sec']}s: {item['result']}；原文：“{item['evidence_text']}”")
    report += ["", "## 边界不确定项", "",
        "- P07 A1/A2/A3 与 B2/B3 边界受连续 ASR 提示回声影响，已按唯一题目词汇和明确转题内容对齐。",
        "- P08 A1 开头 0–90 秒只有广告式 ASR 幻觉，首个可信数学片段从 90 秒开始。",
        "- P09 每题独立文件，题目边界确定；文件内部部分长静音被转成提示回声。", "",
        "## 建议优先复核时间段", "",
    ]
    for participant_id, question_id, item in priority:
        report.append(f"- {participant_id} `{question_id}` {item['start_sec']}–{item['end_sec']}s，confidence {item['confidence']:.2f}：“{item['evidence_text']}”")
    report += ["", "## 泄漏与证据检查", "",
        "- Observed steps 中没有 `ANALYST_INFERENCE`。",
        "- prediction_inputs 仅含当前学生 A 组 trace；不含当前学生 B 组真实数据。",
        "- 本结构化上下文已经读取 P05/P07 的 B 组真实材料，因此没有生成任何盲预测结果。",
        "- 公式听不清时保留 `[ASR_UNCERTAIN: ...]`，没有用标准答案补写。",
        "- 第二周目录仅作为 schema/题目元数据来源，没有被覆盖。", "",
    ]
    if evidence_failures:
        report += ["## Evidence lookup failures", "", *[f"- {item}" for item in evidence_failures], ""]
    if schema_failures:
        report += ["## Schema failures", "", *[f"- {item}" for item in schema_failures], ""]
    (output / "DATA_QUALITY_REPORT.md").write_text("\n".join(report), encoding="utf-8")

    readme = f"""# 第三周音频结构化数据

本目录把第三周 P05–P09 的 audio-first 素材整理成与第二周兼容的学生 trace。

- P05 使用用户提供的带时间戳 A/B 原文。
- P06–P09 使用 Groq `whisper-large-v3` 的音频分段转写，当前均为机器结构化、待人工听音复核。
- 共 {len(traces)} 条 participant × question trace，覆盖 {len(variants)} 道题。
- `prediction_inputs/` 只保留当前参与者 A 组证据，不包含其 B 组真实数据。
- 当前会话已读取真实 B 数据，不能用来声称产生盲预测。

详细限制与优先复核区间见 `DATA_QUALITY_REPORT.md`。
"""
    (output / "README.md").write_text(readme, encoding="utf-8")

    files = sorted(path for path in output.rglob("*") if path.is_file() and path.name != "transfer_manifest.json")
    manifest = {
        "schema_version": "1.0",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "source_repo": str(repo),
        "counts": {
            "participants": len(by_participant), "traces": len(traces),
            "questions_covered": len(variants),
            "observed_steps": sum(len(trace["steps"]) for trace in traces),
            "low_confidence_steps": len(low_conf_steps),
            "evidence_lookup_failures": len(evidence_failures),
            "schema_failures": len(schema_failures),
            "prediction_inputs": len(prediction_participants),
        },
        "participants": sorted(by_participant),
        "prediction_input_participants": prediction_participants,
        "files": [
            {"path": path.relative_to(output).as_posix(), "size_bytes": path.stat().st_size, "sha256": sha256(path)}
            for path in files
        ],
    }
    write_json(output / "transfer_manifest.json", manifest)
    print(json.dumps(manifest["counts"], ensure_ascii=False, indent=2))
    return 1 if evidence_failures or schema_failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
