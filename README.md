# data_process

学生 Think-Aloud / 音视频数据处理与学生解题轨迹（trace）结构化仓库。

## 目录

- `script/`：所有可执行数据处理、转写、结构化、复核与合并脚本。
- `data/raw/`：原始学生素材与题目材料。
- `data/interim/`：转写等中间产物。
- `data/processed/`：第二周主流程生成的结构化结果。
- `data/exports/week2_combinatorics/`：第二周排列组合专项导出（审计用）。
- `data/exports/week3_combinatorics/`：第三周 audio-first 排列组合专项导出（审计用）。
- `data/combined/`：第二周 + 第三周统一后的推荐数据入口。
- `data/reports/`：质量、分析和预测实验报告。
- `configs/`：题库与人工审阅配置。
- `tests/`：处理流程测试。
- `docs/`：流程说明、提示词和历史文档。
- `requirements/`：依赖文件。

后续跨周学生预测实验优先读取 `data/combined/`。统一数据可通过：

```bash
python script/merge_week2_week3.py
```

重新生成。

## Canonical trace schema

后续训练与交互模块默认读取 `data/combined/participant_traces.json`。该文件使用可人工阅读的 pretty JSON，并采用多维 trace schema v2；字段定义见 `data/combined/SCHEMA.md`。
