# Combined student traces

这是后续分析和“学生下一步预测”推荐使用的统一数据入口。

- 第二周主流程：18 traces
- 第三周 audio-first 排列组合：21 traces
- 合计：**39 traces / 9 participants / 12 questions**

文件：
- `participant_traces.jsonl`：统一逐学生逐题 trace。
- `question_trace_variants.json`：基于统一 trace 重新按题目/strategy 聚合。
- `trace_index.json`：记录每条 trace 的周次来源与源素材索引。
- `dataset_manifest.json`：覆盖范围与计数。
- `prediction_inputs/`：第三周已有的预测输入，原样保留。

周次专项导出仍在 `data/exports/`，用于审计和复核。

重新生成：

```bash
python script/merge_week2_week3.py
```
