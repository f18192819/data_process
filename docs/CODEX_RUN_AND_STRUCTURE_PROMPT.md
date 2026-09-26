# Codex 任务：运行音频处理脚本，并整理成第二周格式的结构化学生 trace

仓库：`f18192819/data_process`

## 目标

把当前非结构化学生素材整理成与：

`第二周排列组合结构化数据/`

兼容的结构化 trace，用于后续“小样本 A 组轨迹 → 预测 B 组轨迹”的实验。

当前只做 **audio-first** 版本，不使用视频画面、表情或笔迹推断学生认知。

---

## 0. 参与者与来源约定

第二周已有 P01–P04。

本轮默认：

- `学生素材/1` → `P05`
  - **不要调用 Groq 重新转写**
  - A 组直接读取：`学生素材/1/A组/原文.md`
  - B 组直接读取：`学生素材/1/B组/原文.md`
  - 这两个 Markdown 是带时间戳的用户提供原文，优先级高于视频 ASR。
- `学生素材/2` → `P06`
  - 对 MP4 抽音频并 Groq 转写
- `学生素材/3` → `P07`
  - **当前只处理 `audio.m4a`**
  - 不处理 `video-front.mp4`
  - 不处理 `ink.points.bin`
- `学生素材/4` → `P08`
  - 对 MP4 抽音频并 Groq 转写
- `学生素材/5` → `P09`
  - 直接处理 `A1.m4a`、`A2.m4a`、`A3.m4a`

如果 `media_inventory.json` 中参与者映射不同，以 inventory 为准。

---

# 1. 先检查环境与仓库

在仓库根目录执行。

首先确认：

```powershell
git status
git lfs install
git lfs pull
```

然后确认 FFmpeg：

```powershell
ffmpeg -version
ffprobe -version
```

安装 Python 依赖：

```powershell
pip install -r requirements_audio.txt
```

Groq key **只能从环境变量读取，不得写入脚本、Markdown、JSON、日志或 commit**。

检查：

```powershell
if ($env:GROQ_API_KEY) { "GROQ_API_KEY is set" } else { "GROQ_API_KEY is NOT set" }
```

如果未设置，停止并要求用户在 PowerShell 中设置：

```powershell
$env:GROQ_API_KEY="<new Groq API key>"
```

不要把 key 输出到终端。

---

# 2. 先运行 dry-run

执行：

```powershell
python process_student_media.py --dry-run
```

检查输出应满足：

- 不出现 `学生素材/1` 的视频；
- 出现 `学生素材/2`；
- `学生素材/3` 只出现 `audio.m4a`，不能出现 `video-front.mp4`；
- 出现 `学生素材/4`；
- 出现 `学生素材/5/A1.m4a`、`A2.m4a`、`A3.m4a`。

如果学生 2/4 的 MP4 显示 `[LFS POINTER]`，先执行：

```powershell
git lfs pull
```

再 dry-run。

不要在 LFS pointer 上继续 FFmpeg。

---

# 3. 正式调用脚本

确认 dry-run 正常后执行：

```powershell
python process_student_media.py
```

默认：

- `whisper-large-v3`
- 中文 `zh`
- 16 kHz mono FLAC
- 480 秒 chunk
- 3 秒 overlap
- segment timestamp

如需更细粒度 word timestamp：

```powershell
python process_student_media.py --word-timestamps --force
```

第一轮 trace 分段通常 segment timestamp 即可，不要无必要重跑。

脚本输出目录：

```text
音频转写_待结构化/
├── media_inventory.json
├── processing_summary.json
├── P06/
├── P07/
├── P08/
└── P09/
```

每个 session 重点读取：

```text
session_manifest.json
transcript_segments.jsonl
transcript.txt
```

`raw_groq/` 只用于核查底层 ASR。

---

# 4. 结构化前必须阅读第二周 schema

依次阅读：

1. `conversation_with_chen.md`
2. `第二周排列组合结构化数据/README.md`
3. `第二周排列组合结构化数据/question_metadata_combinatorics.json`
4. `第二周排列组合结构化数据/participant_traces_combinatorics.jsonl`
5. `第二周排列组合结构化数据/reviewed_trace_annotations_combinatorics.json`
6. `第二周排列组合结构化数据/question_trace_variants_combinatorics.json`
7. `第二周排列组合结构化数据/transfer_manifest.json`

不要只凭 README 猜字段；必须实际查看 JSON/JSONL 中已有记录。

---

# 5. 处理 P05：直接使用“原文.md”

P05 不使用 Groq ASR。

读取：

```text
学生素材/1/A组/原文.md
学生素材/1/B组/原文.md
```

文件中的形式类似：

```text
徐伊芃 06:04
...
徐伊芃 06:51
...
```

将 `mm:ss` 转换为秒：

```text
06:04 -> 364.0
06:51 -> 411.0
```

每条 utterance：

- `start_sec` = 当前时间戳
- `end_sec` = 下一条 utterance 的 start_sec
- 最后一条可以令 `end_sec = null`，或使用组录音时长（若可可靠获得）
- 原文措辞作为 `evidence_text`，不要再通过 Groq 改写

P05 的 `source_type`：

`user_provided_timestamped_transcript`

A/B 组边界由文件夹直接确定，不需要重新猜组别，但仍需要在每组内部对齐 A1/A2/A3 或 B1/B2/B3。

---

# 6. 处理 P06–P09：读取脚本输出

优先读取：

```text
音频转写_待结构化/<PID>/sessions/*/transcript_segments.jsonl
```

`review_required=true` 的片段要优先人工/音频复核。

不要因为你知道标准答案而“修正”数学内容。

例如 ASR：

```text
CN加M减一M
```

如果无法从音频可靠确认组合数上下标，就保留：

```text
[ASR_UNCERTAIN: 组合数上下标无法确认]
```

而不是自动恢复成标准公式。

---

# 7. 题目对齐

使用：

`第二周排列组合结构化数据/question_metadata_combinatorics.json`

中的 `canonical_text` 和 `signals`。

优先级：

1. 文件名/目录明确题号：
   - `A1.m4a` → `COMB_A1`
   - `A2.m4a` → `COMB_A2`
   - `A3.m4a` → `COMB_A3`
2. 文件夹明确组别：
   - `A组` → `COMB_A`
   - `B组` → `COMB_B`
3. 长录音中使用：
   - “第一题/第二题/第三题/下一题/最后一道”
   - 题目独特词汇
   - question signals

每个题目 segment 输出：

```json
{
  "slot": 1,
  "question_id": "COMB_A1",
  "start_sec": 0.0,
  "end_sec": 133.96,
  "boundary_confidence": 0.95,
  "boundary_rationale": "...",
  "text": "简短过程摘要"
}
```

无法可靠对齐时，不硬猜。

---

# 8. reasoning step 切分

原则：

**一个认知动作 = 一个 step，而不是一句话 = 一个 step。**

优先沿用第二周已有 action ontology：

- `ATTEND`
- `RECALL`
- `REPRESENT`
- `PLAN`
- `BRANCH`
- `CLASSIFY`
- `ENUMERATE`
- `DERIVE`
- `CALCULATE`
- `CHECK`
- `HESITATE`
- `STUCK`
- `BACKTRACK`
- `CORRECT`
- `ABANDON`
- `ANSWER`

每个 step 使用第二周兼容字段：

```json
{
  "start_sec": 32.0,
  "end_sec": 51.0,
  "evidence_text": "所以相当于把这个……呃……应该……",
  "signal_refs": ["C1"],
  "action_type": "HESITATE",
  "content": "尚未形成明确计数方案，出现停顿和试探。",
  "correctness": "not_applicable",
  "status": "VERBALIZED",
  "confidence": 0.98,
  "step_id": "s02",
  "order": 2,
  "clean_text": "所以相当于把这个……呃……应该……",
  "representation": null,
  "result": null
}
```

---

# 9. 严格区分 observed 与 inference

这是最重要的数据质量规则。

如果学生说：

```text
“我感觉可以用补集”
```

可以记录：

```text
PLAN(complement)
status = VERBALIZED
```

如果学生没说，但从标准解法看“应该用了补集”，不能写进 observed steps。

只能放：

```json
{
  "content": "研究者推测此处可能在考虑补集，但语音证据不足。",
  "status": "ANALYST_INFERENCE",
  "confidence": 0.55
}
```

`ANALYST_INFERENCE` 不进入 `path_signature`。

---

# 10. first_attention / first reaction

每道题都尽量提取：

```json
"first_attention": {
  "signal_refs": ["S2"],
  "operation": "ATTEND",
  "evidence": "...",
  "confidence": 0.95
}
```

必须是进入该题后**最早的有意义认知反应**。

不要把后面成熟策略倒填为第一反应。

“完全不会”“是不是卡特兰”“为什么这里是7个数”等都可能是有效第一反应。

---

# 11. strategy 与 path_signature

`strategy` 用稳定 snake_case，例如：

```text
gap_insertion_then_complement
dynamic_programming_recurrence
catalan_check_then_reflection
occupancy_partition_enumeration
stuck_then_pigeonhole_attempt
```

`path_signature` 必须从 observed steps 顺序压缩得到，例如：

```json
[
  "ATTEND(C1)",
  "HESITATE",
  "PLAN(arrange-boys-first)",
  "REPRESENT(internal-gaps)",
  "BACKTRACK",
  "PLAN(complement-adjacent-AB)",
  "ANSWER"
]
```

不要根据标准解法生成。

---

# 12. correctness 与 confidence

`correctness` 优先使用第二周已有值：

- `correct`
- `partially_correct`
- `uncertain`
- `not_applicable`

`trace_confidence` 反映：

“我们是否可靠地记录了学生真实过程”

而不是学生能力。

ASR差、公式听不清、串音多、边界模糊 → confidence 降低。

学生做错题本身不应该导致 trace_confidence 降低。

---

# 13. 生成第三周结构化目录

新建：

```text
第三周_音频结构化数据/
├── README.md
├── reviewed_trace_annotations_combinatorics.json
├── participant_traces_combinatorics.jsonl
├── question_trace_variants_combinatorics.json
├── question_metadata_combinatorics.json
├── prediction_inputs/
└── transfer_manifest.json
```

不要覆盖第二周文件。

`question_metadata_combinatorics.json` 从第二周复制，保持 question ID / signals 一致。

---

# 14. reviewed 文件的 source_type

P05：

```text
user_provided_timestamped_transcript
```

P06/P07/P08/P09，如果尚未人工听音复核：

```text
groq_whisper_large_v3_audio_only_machine_structured_pending_human_review
```

只有真正人工核对音频后，才允许改成：

```text
groq_whisper_large_v3_audio_only_reviewed
```

不要把机器结构化结果冒充人工审定。

---

# 15. participant trace 主文件

`participant_traces_combinatorics.jsonl`

每行 = 一个参与者 × 一道题。

保持第二周核心字段：

```text
trace_id
question_id
question_slot
trace_confidence
first_attention
strategy
path_signature
steps
analyst_inferences
participant_id
assigned_group
```

可以额外添加：

```text
source_relative_path
source_modalities
session_id
source_type
```

但不要破坏核心字段。

---

# 16. question_trace_variants

按照第二周聚合逻辑生成：

```text
n_participants
participants
trace_families
common_prefix
first_meaningful_divergence
```

不要因为一题只有一个学生而虚构多个 trace family。

---

# 17. 给 A→B 预测准备独立输入

为拥有 A 组数据的学生生成：

```text
第三周_音频结构化数据/prediction_inputs/P05_from_A.json
P06_from_A.json
...
```

只包含：

- A1/A2/A3 的 first_attention
- strategy
- path_signature
- observed steps
- 明确分开的 analyst_inferences

**不能包含该学生 B 组真实数据。**

---

# 18. 防止预测泄漏

做真实 A→B 预测时：

1. 先把真实 A/B 数据全部结构化并冻结；
2. 再打开一个新的 Codex 会话 / 新运行上下文；
3. 只给预测模型：
   - `Pxx_from_A.json`
   - B 组 question metadata
   - 允许作为 retrieval corpus 的“其他历史学生”记录
4. 不给当前学生自己的 B transcript / B trace；
5. 输出并保存 prediction；
6. prediction 文件落盘后才读取当前学生真实 B gold；
7. 最后评价。

如果某个 Codex 上下文已经读取过当前学生真实 B，不能把该上下文产生的结果算作盲预测。

---

# 19. 第一轮预测指标

先预测这些结构化目标：

- `first_attention`
- `first_strategy`
- `primary_strategy`
- `path_signature`
- 是否 `STUCK`
- 是否 `BACKTRACK`
- 是否 `CORRECT` / self-correct
- 是否完成

完整自然语言 trace 可以附加生成，但不使用字符串完全相等作为主指标。

---

# 20. 最终数据质量检查

完成后检查：

1. 每个 `evidence_text` 能否在原文/ASR transcript 中找到；
2. 有没有根据标准答案补写学生没说的步骤；
3. `ANALYST_INFERENCE` 有没有混入 observed path；
4. step 时间是否落在对应题目 segment；
5. `path_signature` 是否与 step 顺序一致；
6. `first_attention` 是否真的是第一反应；
7. 听不清的公式是否被错误恢复为标准公式；
8. P05 是否确实只使用 `原文.md`；
9. P07 是否确实只使用 student 3 的 `audio.m4a`；
10. 是否没有覆盖第二周数据。

最后生成一份 `DATA_QUALITY_REPORT.md`，列出：

- 每个参与者识别到哪些题；
- 每题 step 数；
- 低置信度片段数量；
- 待人工复核公式；
- 无法确定的题目边界；
- 建议优先复核的时间段。
