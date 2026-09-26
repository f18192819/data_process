# Combined student traces

这是后续分析、学生预测与交互模块推荐使用的统一数据入口。

- 第二周主流程：18 traces
- 第三周 audio-first 排列组合：21 traces
- 合计：**39 traces / 9 participants / 12 questions**

## 推荐文件

- `participant_traces.json`：schema v2 的统一 trace，使用标准 JSON 缩进，可直接人工阅读。
- `SCHEMA.md`：operation / control / cognitive_state / correctness 定义。
- `question_trace_variants.json`：按题目/strategy 聚合；为了历史可比性仍保留 legacy path signature。
- `trace_index.json`：记录每条 trace 的周次来源与源素材索引。
- `dataset_manifest.json`：覆盖范围与计数。
- `prediction_inputs/`：同样已迁移到 schema v2。

历史周次导出仍在 `data/exports/`，保持旧 schema，不改写，用于审计和复核。

重新生成：

```bash
python script/merge_week2_week3.py
```
