# 第三周音频结构化数据

本目录把第三周 P05–P09 的 audio-first 素材整理成与第二周兼容的学生 trace。

- P05 使用用户提供的带时间戳 A/B 原文。
- P06–P09 使用 Groq `whisper-large-v3` 的音频分段转写，当前均为机器结构化、待人工听音复核。
- 共 21 条 participant × question trace，覆盖 6 道题。
- `prediction_inputs/` 只保留当前参与者 A 组证据，不包含其 B 组真实数据。
- 当前会话已读取真实 B 数据，不能用来声称产生盲预测。

详细限制与优先复核区间见 `DATA_QUALITY_REPORT.md`。
