# 第三周 audio-first 处理说明

当前设计：

- Student 1 / P05：**不跑 Groq**，直接用：
  - `学生素材/1/A组/原文.md`
  - `学生素材/1/B组/原文.md`
- Student 2 / P06：MP4 → 音频 → Groq
- Student 3 / P07：**只处理 `audio.m4a`**
- Student 4 / P08：MP4 → 音频 → Groq
- Student 5 / P09：A1/A2/A3 `.m4a` → Groq

## 重要：API Key

脚本不会也不应保存 Groq API Key。

在 PowerShell 临时设置：

```powershell
$env:GROQ_API_KEY="<your Groq API key>"
```

不要把 key 写入仓库。

## 环境准备

```powershell
git lfs install
git lfs pull
pip install -r requirements_audio.txt
```

确认：

```powershell
ffmpeg -version
ffprobe -version
```

## 检查媒体发现

```powershell
python process_student_media.py --dry-run
```

应只发现 student 2/3/4/5 的媒体；student 3 只能出现 `audio.m4a`。

## 正式转写

```powershell
python process_student_media.py
```

可选 word timestamps：

```powershell
python process_student_media.py --word-timestamps --force
```

## 输出

```text
音频转写_待结构化/
├── media_inventory.json
├── processing_summary.json
├── P06/
├── P07/
├── P08/
└── P09/
```

## 下一步

把 `CODEX_RUN_AND_STRUCTURE_PROMPT.md` 整段交给 Codex。

它会：

1. 调用本脚本完成 ASR；
2. 读取 P05 的原文 Markdown；
3. 读取第二周结构化 schema；
4. 逐题对齐；
5. 切 reasoning steps；
6. 生成 first_attention / strategy / path_signature；
7. 输出第三周结构化数据；
8. 为 A→B 预测生成只含 A 数据的 `prediction_inputs/`；
9. 做数据质量检查。
