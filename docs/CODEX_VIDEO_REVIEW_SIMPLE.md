# Codex：直接完成视频辅助 Trace 复核

仓库：`f18192819/data_process`

目标：直接使用仓库中的视频辅助检查并修改第三周 trace。不要让我手动逐个运行命令。你自己完成全部流程。

## 要做的事

1. 先阅读：
   - `第三周_音频结构化数据/participant_traces_combinatorics.jsonl`
   - `第三周_音频结构化数据/DATA_QUALITY_REPORT.md`
   - `第三周_音频结构化数据/reviewed_trace_annotations_combinatorics.json`
   - `video_trace_review.py`

2. 在仓库根目录先执行：
   ```powershell
   git lfs pull
   python video_trace_review.py list
   ```

3. 按 `list` 发现的视频逐个处理，一次只处理一个。

4. 对每个视频执行：
   ```powershell
   python video_trace_review.py prepare --video-id "<video_id>"
   ```
   默认每 10 秒一张图。

5. 查看该视频生成的：
   - `frame_manifest.json`
   - `linked_traces.jsonl`
   - `frames/`

6. 优先检查：
   - 低 confidence step；
   - `[ASR_UNCERTAIN: ...]`；
   - 数学公式；
   - `STUCK / CHECK / BACKTRACK / CORRECT`；
   - 长时间沉默但可能在书写；
   - 题目切换边界。

7. 如果 10 秒一张不够，在局部时间段自行调用：
   ```powershell
   python video_trace_review.py zoom `
     --video-id "<video_id>" `
     --start <开始秒数> `
     --end <结束秒数> `
     --interval 1
   ```

8. 根据视频**可直接观察到的证据**修改 trace：
   - 可以核实手写公式；
   - 可以补充只写没说的可见步骤；
   - 可以确认划掉、重写、换方法；
   - 可以修正题目切换时间。

   不允许：
   - 从表情推断困惑、焦虑、信心；
   - 从姿势/视线推断学生正在想什么；
   - 根据标准答案补学生没有说、没有写的推理。

9. 如果某个视频只是前置摄像头，看不到纸面或屏幕，就不要强行修改 trace。

10. 按 `video_trace_review.py` 现有流程，把需要改的完整 trace 写到当前视频临时目录的：
    ```text
    trace_replacements.jsonl
    ```
    同时写：
    ```text
    review_notes.json
    ```
    必要时写：
    ```text
    segment_updates.json
    ```

11. 每处理完一个视频，立刻执行：
    ```powershell
    python video_trace_review.py finalize --video-id "<video_id>"
    ```
    确认 trace 已经更新，并且该视频的临时图片已经被删除，然后再处理下一个视频。

12. 如果脚本有小问题，允许你直接修改 `video_trace_review.py` 后继续执行，但不要改变研究数据的基本 schema。

## 最重要的清理要求

所有视频处理完成后：

1. 确认：
   ```powershell
   Test-Path .video_review_tmp
   ```
   应该返回 `False`。

2. 删除所有本次视频分析产生的：
   - 抽帧 JPG/PNG；
   - zoom 图片；
   - 临时 frame 目录；
   - 中间视频文件（如果你额外生成过）；
   - 临时 review workspace。

3. **不要删除原始视频。**
4. **不要删除仓库中原本就存在的学生图片、PDF、音频或原始素材。**
5. 只删除这次视频辅助分析新生成的临时图像和中间文件。

## 最后检查

处理结束后重新检查：

- `第三周_音频结构化数据/participant_traces_combinatorics.jsonl`
- `reviewed_trace_annotations_combinatorics.json`
- `question_trace_variants_combinatorics.json`
- `prediction_inputs/`
- `VIDEO_REVIEW_LOG.jsonl`

保证结构仍然兼容第二周。

最后给我一个简短报告，说明：

- 实际处理了哪些视频；
- 哪些 trace 被修改；
- 哪些低置信问题被视频解决；
- 哪些视频没有提供有效数学证据；
- 最终 `.video_review_tmp` 是否已删除；
- 是否还存在任何本次生成的临时图片。
