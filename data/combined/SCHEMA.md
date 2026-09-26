# Student trace schema v2

`data/combined/participant_traces.json` 是后续训练与交互系统推荐使用的 canonical 数据。

## 为什么拆分

旧版把 `CALCULATE / HESITATE / STUCK / BACKTRACK / CORRECT / ABANDON` 等不同维度都放进一个互斥的 `action_type`。v2 将它拆成：

- **operation**：学生正在进行什么认知/解题操作。
- **control**：路径控制事件，如分支、回退、放弃。
- **cognitive_state**：可观察到的犹豫/卡住状态。
- **correctness**：该步骤内容的正确性。
- **revision**：是否明确是在修正之前的内容。

## operation

当前主类别：

`ATTEND / RECALL / REPRESENT / PLAN / REASON / COMPUTE / CHECK / RESPOND`

旧标签映射：

- `TRANSFORM → REPRESENT`
- `CLASSIFY / ENUMERATE / DERIVE → REASON`
- `CALCULATE → COMPUTE`
- `ANSWER → RESPOND`

## control

允许值：`CONTINUE / BRANCH / BACKTRACK / ABANDON`。

**迁移时不会因为没有控制事件就自动写 CONTINUE。** 没有证据时：

```json
{"value": null, "status": "UNKNOWN", "confidence": null}
```

## cognitive_state

允许值：`NORMAL / HESITATING / STUCK`。

同样，**UNKNOWN != NORMAL**。旧数据只有明确的 `HESITATE` 和 `STUCK` 会迁移出状态标签。

## 示例

```json
{
  "step_id": "s05",
  "content": "尝试计算剩余排列数",
  "operation": {
    "value": "COMPUTE",
    "subtype": "CALCULATE",
    "status": "OBSERVED",
    "confidence": 0.88
  },
  "control": {
    "value": null,
    "subtype": null,
    "status": "UNKNOWN",
    "confidence": null
  },
  "cognitive_state": {
    "value": null,
    "subtype": null,
    "status": "UNKNOWN",
    "confidence": null
  }
}
```

## 迁移原则

历史 `data/exports/` 不改写，继续作为审计来源。canonical `data/combined/` 使用 v2。每个 step 保留 `legacy_action_type`，便于追溯旧标签，但后续训练建议使用新的多维字段。
