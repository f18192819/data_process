# Trace 粒度审计

> 审计目标：确认每名参与者都按可观察反应拆成原子步骤，而不是只保留方法名称或最终答案。证据不足时保持短 trace 与低置信度，不补写思路。

## 审计标准

- 每个 observed step 必须有原始证据文本；
- 注意、回忆、表示转换、计算、分支、回退、纠正、卡住和情绪反应分别记录；
- `ANALYST_INFERENCE` 不得出现在 observed steps；
- 录音/材料缺失造成的粗粒度必须显式标记 confidence 和人工复核项；
- 正确答案不能用于倒推出未口述的中间步骤。

## 逐 trace 检查

| Participant | Question | Steps | Evidence statuses | Revision/error events | Trace confidence | Audit finding |
|---|---:|---:|---|---|---:|---|
| P01 | COMB_A1 | 7 | VERBALIZED | BACKTRACK | 0.78 | 已拆分为逐反应/逐操作步骤 |
| P01 | COMB_A2 | 4 | VERBALIZED | none | 0.76 | 已拆分为逐反应/逐操作步骤 |
| P01 | COMB_A3 | 6 | VERBALIZED | none | 0.90 | 已拆分为逐反应/逐操作步骤 |
| P02 | COMB_A1 | 12 | VERBALIZED | HESITATE, BACKTRACK | 0.86 | 已拆分为逐反应/逐操作步骤 |
| P02 | COMB_A2 | 10 | VERBALIZED | BACKTRACK | 0.84 | 已拆分为逐反应/逐操作步骤 |
| P02 | COMB_A3 | 7 | VERBALIZED | none | 0.95 | 已拆分为逐反应/逐操作步骤 |
| P03 | COMB_B1 | 5 | VERBALIZED | none | 0.60 | 证据受限；保留细节与低置信度，未补全过程 |
| P03 | COMB_B2 | 4 | VERBALIZED | none | 0.70 | 证据受限；保留细节与低置信度，未补全过程 |
| P03 | COMB_B3 | 2 | VERBALIZED | STUCK | 0.80 | 原始反应本身很短；未扩写不存在的中间步骤 |
| P04 | COMB_C1 | 6 | VERBALIZED | CORRECT, ABANDON | 0.72 | 证据受限；保留细节与低置信度，未补全过程 |
| P04 | COMB_C2 | 5 | VERBALIZED | none | 0.94 | 已拆分为逐反应/逐操作步骤 |
| P04 | COMB_C3 | 6 | STRONGLY_IMPLIED, VERBALIZED | none | 0.93 | 已拆分为逐反应/逐操作步骤 |
| P05 | TRIG_A1 | 4 | VERBALIZED | none | 0.94 | 已拆分为逐反应/逐操作步骤 |
| P05 | TRIG_A2 | 3 | STRONGLY_IMPLIED, VERBALIZED | none | 0.88 | 已拆分为逐反应/逐操作步骤 |
| P05 | TRIG_A3 | 3 | STRONGLY_IMPLIED, VERBALIZED | STUCK, ABANDON | 0.96 | 已拆分为逐反应/逐操作步骤 |
| P06 | TRIG_A1 | 7 | STRONGLY_IMPLIED, WRITTEN_OBSERVED | HESITATE, ERROR, BACKTRACK, CORRECT | 0.96 | 已拆分为逐反应/逐操作步骤 |
| P06 | TRIG_A2 | 2 | WRITTEN_OBSERVED | none | 0.95 | 原始反应本身很短；未扩写不存在的中间步骤 |
| P06 | TRIG_A3 | 12 | WRITTEN_OBSERVED | none | 0.98 | 已拆分为逐反应/逐操作步骤 |

## Participant-level conclusion

- **P01**：三个问题均保留了方法选择、分支和递推状态；A1 的第二方案及回退单独记录。
- **P02**：已依据用户提供的带时间戳原文重建。A1 保留三个小问、间隔计数的两次尝试、明确回退、捆绑法与补集法；A2 保留格路建模、Catalan 类比、自我质疑以及总路径减反射坏路径；A3 保留两种余数情况和抽屉论证。游戏/聊天串音已排除，听不清的公式仍标记不确定。
- **P03**：B1 的正方形总数存在 ASR 歧义，B2 只观察到人数拆分枚举，B3 只观察到‘无法理解→仍尝试抽屉原理’；这些限制均被保留。
- **P04**：C1 的分类、自我纠正和停止求和分开记录；C2/C3 的表示转换与公式操作逐步记录。
- **P05**：来源是无时间戳汇总文本。A1/A2 保留明确口述，A3 只记录‘不会做/公式忘了/停止’，没有把第三人称补充说明改写成学生步骤。
- **P06**：A1 保留否认、单调性调用、领域误读、回退、注意 `+2kπ`、概念修正及情绪反应；A2 明确保留未口述的中间依据；A3 按手写等式逐步拆分。

## Result

现有 P01–P06 的底层 trace 按原子反应/操作展示证据、动作、正确性、状态与 confidence。P02 已用用户提供原文替换早期粗粒度版本；P03 的少数 trace 仍较短，因为可辨认原始证据不足，继续细化会构成猜测。
