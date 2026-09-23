# 第三周 Audio-first 数据质量报告

生成时间：`2026-09-23T17:12:46.315263+00:00`

## 范围

- P05：仅使用 A组/B组 `原文.md`，未调用 Groq。
- P06/P08：仅使用 MP4 抽取音频后的 Groq 分段转写。
- P07：仅使用 `audio.m4a`；没有读取视频或笔迹来推断认知。
- P09：使用 A1/A2/A3 三段 M4A 的 Groq 分段转写。

## 题目与 step 数

| Participant | Questions | Steps | Source type |
|---|---|---:|---|
| P05 | COMB_A1 | 9 | `user_provided_timestamped_transcript` |
| P05 | COMB_A2 | 10 | `user_provided_timestamped_transcript` |
| P05 | COMB_A3 | 11 | `user_provided_timestamped_transcript` |
| P05 | COMB_B1 | 5 | `user_provided_timestamped_transcript` |
| P05 | COMB_B2 | 10 | `user_provided_timestamped_transcript` |
| P05 | COMB_B3 | 6 | `user_provided_timestamped_transcript` |
| P06 | COMB_B1 | 7 | `groq_whisper_large_v3_audio_only_machine_structured_pending_human_review` |
| P06 | COMB_B2 | 4 | `groq_whisper_large_v3_audio_only_machine_structured_pending_human_review` |
| P06 | COMB_B3 | 7 | `groq_whisper_large_v3_audio_only_machine_structured_pending_human_review` |
| P07 | COMB_A1 | 3 | `groq_whisper_large_v3_audio_only_machine_structured_pending_human_review` |
| P07 | COMB_A2 | 4 | `groq_whisper_large_v3_audio_only_machine_structured_pending_human_review` |
| P07 | COMB_A3 | 5 | `groq_whisper_large_v3_audio_only_machine_structured_pending_human_review` |
| P07 | COMB_B1 | 6 | `groq_whisper_large_v3_audio_only_machine_structured_pending_human_review` |
| P07 | COMB_B2 | 1 | `groq_whisper_large_v3_audio_only_machine_structured_pending_human_review` |
| P07 | COMB_B3 | 5 | `groq_whisper_large_v3_audio_only_machine_structured_pending_human_review` |
| P08 | COMB_A1 | 5 | `groq_whisper_large_v3_audio_only_machine_structured_pending_human_review` |
| P08 | COMB_A2 | 8 | `groq_whisper_large_v3_audio_only_machine_structured_pending_human_review` |
| P08 | COMB_A3 | 7 | `groq_whisper_large_v3_audio_only_machine_structured_pending_human_review` |
| P09 | COMB_A1 | 8 | `groq_whisper_large_v3_audio_only_machine_structured_pending_human_review` |
| P09 | COMB_A2 | 8 | `groq_whisper_large_v3_audio_only_machine_structured_pending_human_review` |
| P09 | COMB_A3 | 7 | `groq_whisper_large_v3_audio_only_machine_structured_pending_human_review` |

## 质量统计

- Participants: 5
- Traces: 21
- Observed steps: 136
- Low-confidence steps (<0.75): 52
- Formula spans pending review: 15
- Evidence lookup failures: 0
- Schema/ordering failures: 0

## 待人工复核公式

- P05 `COMB_B2` 1903–1957s: [ASR_UNCERTAIN: 9! multiplied by a combination number]；原文：“因为他这里。九的全排列，所以是 p99再乘以 C 的15。”
- P06 `COMB_B1` 477–495s: [ASR_UNCERTAIN: square-count summation]；原文：“6加5加4加3加2加1。”
- P06 `COMB_B2` 577–594s: [ASR_UNCERTAIN: occupancy equation]；原文：“那如果我的X,SE加什么什么加X,最后应该是等我9个人进站。”
- P06 `COMB_B2` 652–683s: [ASR_UNCERTAIN: summation formula]；原文：“1加6s2加a6s3,1加到a6si”
- P06 `COMB_B3` 1228.333–1262.493s: [ASR_UNCERTAIN: ratio of powers of two]；原文：“必然存在某两个数”
- P07 `COMB_A1` 65–84s: [ASR_UNCERTAIN: m/n indices]；原文：“M 就是 M 加 1 的阶层,然后再看 M 女生本身是 M 阶层。”
- P07 `COMB_A1` 114–126s: [ASR_UNCERTAIN: likely total minus adjacent count]；原文：“M加n的介绍解析,两倍的M加n-e的介绍。对。”
- P07 `COMB_B1` 899–945.88s: [ASR_UNCERTAIN: point-pair formula]；原文：“首先,C812是80个点里,认取两个点的各数中,它们要减去。”
- P07 `COMB_B1` 1099–1149.68s: [ASR_UNCERTAIN: side-length products]；原文：“在横向上可以有9个数学生规划,有7种不同的系统。”
- P07 `COMB_B3` 1832–1845.68s: [ASR_UNCERTAIN: definition of q bins]；原文：“那么这样不同的Q的几个组数呢,我们这种就怕要算是n组。”
- P08 `COMB_A1` 233.14–237s: [ASR_UNCERTAIN: combination indices]；原文：“所以现在就是c n-m-a。词中有数字,请读。”
- P08 `COMB_A1` 295–322s: [ASR_UNCERTAIN: permutation product]；原文：“试习后,还要对女生进行一个全排列。”
- P09 `COMB_A1` 257–294.5s: [ASR_UNCERTAIN: remaining gap factor]；原文：“女生先进行全排列,就是m的,不是,n的阶层”
- P09 `COMB_A1` 556.376–584.676s: [ASR_UNCERTAIN: A/B insertion formula]；原文：“只要是不相连,它基本上都插空站。”
- P09 `COMB_A2` 473.8–496s: [ASR_UNCERTAIN: total path combination indices]；原文：“横杠书冠它本身是没有什么要求的嘛”

## 边界不确定项

- P07 A1/A2/A3 与 B2/B3 边界受连续 ASR 提示回声影响，已按唯一题目词汇和明确转题内容对齐。
- P08 A1 开头 0–90 秒只有广告式 ASR 幻觉，首个可信数学片段从 90 秒开始。
- P09 每题独立文件，题目边界确定；文件内部部分长静音被转成提示回声。

## 建议优先复核时间段

- P07 `COMB_B3` 1576–1585s，confidence 0.32：“把这个课将把n个数分出。”
- P07 `COMB_A2` 475–479.28s，confidence 0.35：“我给大家映射了一条合法的录音室。”
- P07 `COMB_B3` 1832–1845.68s，confidence 0.35：“那么这样不同的Q的几个组数呢,我们这种就怕要算是n组。”
- P08 `COMB_A1` 233.14–237s，confidence 0.35：“所以现在就是c n-m-a。词中有数字,请读。”
- P07 `COMB_A3` 701.26–731s，confidence 0.38：“在这五个队作为模10的语书的意义下,那么这七个里面必定有两个位于同一队的。”
- P07 `COMB_A3` 823–862s，confidence 0.40：“只有两个数可以选了。所以这会就是我们的一次这样的证明了。”
- P07 `COMB_A1` 114–126s，confidence 0.42：“M加n的介绍解析,两倍的M加n-e的介绍。对。”
- P07 `COMB_A3` 682–690.88s，confidence 0.45：“模10以下呼应。”
- P07 `COMB_A3` 791–823s，confidence 0.45：“前四组如果任意有有两个是同一组,直接整理。”
- P06 `COMB_B2` 652–683s，confidence 0.48：“1加6s2加a6s3,1加到a6si”
- P07 `COMB_B1` 899–945.88s，confidence 0.48：“首先,C812是80个点里,认取两个点的各数中,它们要减去。”
- P07 `COMB_A1` 65–84s，confidence 0.50：“M 就是 M 加 1 的阶层,然后再看 M 女生本身是 M 阶层。”
- P07 `COMB_B1` 1099–1149.68s，confidence 0.50：“在横向上可以有9个数学生规划,有7种不同的系统。”
- P07 `COMB_B2` 1212.56–1220.76s，confidence 0.52：“这九个球变成一样的状态是把九个球放到六个盒子里”
- P06 `COMB_B2` 577–594s，confidence 0.55：“那如果我的X,SE加什么什么加X,最后应该是等我9个人进站。”
- P06 `COMB_B3` 920.34–940s，confidence 0.55：“把所有的写成”
- P07 `COMB_A2` 291.86–316.94s，confidence 0.55：“如果有一种走法是不接触这条直线的对称的话”
- P07 `COMB_A3` 559–561s，confidence 0.55：“OK,重要的是7个不同的正等数。”
- P07 `COMB_B3` 1511–1537s，confidence 0.55：“3.6是一段。”
- P07 `COMB_B3` 1875.68–1910.96s，confidence 0.55：“例如,n等于2的时候是1,2,3,4。”

## 泄漏与证据检查

- Observed steps 中没有 `ANALYST_INFERENCE`。
- prediction_inputs 仅含当前学生 A 组 trace；不含当前学生 B 组真实数据。
- 本结构化上下文已经读取 P05/P07 的 B 组真实材料，因此没有生成任何盲预测结果。
- 公式听不清时保留 `[ASR_UNCERTAIN: ...]`，没有用标准答案补写。
- 第二周目录仅作为 schema/题目元数据来源，没有被覆盖。
