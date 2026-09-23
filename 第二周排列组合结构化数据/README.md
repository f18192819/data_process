# 第二周排列组合学生作答结构化数据

本目录由第二周数据中所有 `COMB_*` 记录筛选生成，供第三周继续分析。第二周源数据未被移动或修改。

## 内容

- `participant_traces_combinatorics.jsonl`：逐学生、逐题 trace，共 12 条。
- `question_trace_variants_combinatorics.json`：逐题跨学生聚合，共 9 道题。
- `reviewed_trace_annotations_combinatorics.json`：P01–P04 的审定分段、对齐和 trace 标注。
- `question_metadata_combinatorics.json`：题目文字与 signals，不包含答案键。
- `transfer_manifest.json`：导出范围、计数和文件校验值。

## 范围

- 参与者：P01, P02, P03, P04
- 题目：COMB_A1, COMB_A2, COMB_A3, COMB_B1, COMB_B2, COMB_B3, COMB_C1, COMB_C2, COMB_C3
- 每名参与者 trace 数：{'P01': 3, 'P02': 3, 'P03': 3, 'P04': 3}
- 每题 trace 数：{'COMB_A1': 2, 'COMB_A2': 2, 'COMB_A3': 2, 'COMB_B1': 1, 'COMB_B2': 1, 'COMB_B3': 1, 'COMB_C1': 1, 'COMB_C2': 1, 'COMB_C3': 1}

P02 使用 2026-09-21 用户提供的带时间戳原文重建；其公式转写不确定项和游戏/聊天串音处理保留在 trace 与 analyst inference 字段中。
