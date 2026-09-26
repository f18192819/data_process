# Repository restructure

本次重构从“按周次堆目录”改为“按数据生命周期组织”：

```text
script/
data/
  raw/
  interim/
  processed/
  exports/
  combined/
  reports/
configs/
tests/
docs/
requirements/
```

同时删除两个完全重复的文件：`process_student_media_v2.py` 与 `requirements_audio_v2.txt`。旧路径仍可从 Git 历史恢复。
