# G0 / G1 / G2 / G3 与真实 B 组 Trace 对比报告

## 1. 数据范围

真实 B 组 gold 来自当前仓库 `第三周_音频结构化数据/participant_traces_combinatorics.jsonl`。

- P05：B1/B2/B3 均有 gold，平均 `trace_confidence ≈ 0.933`。
- P06：B1/B2/B3 均有 gold。
- P07：B1/B2/B3 均有 gold，但平均 `trace_confidence ≈ 0.467`，因此可靠性明显低于 P05。
- P08/P09 虽然有 G1/G3 预测，但当前没有真实 B gold，因此不参与评分。

四组完全公平比较只能使用 **P05 + P07，共 6 条 B trace**。G0 与 G2 还可以额外在 P06 上比较，因此二者另有 9 条扩展结果。

## 2. 评分方法

本报告没有比较自然语言文本是否完全一致，而是使用五个结构化指标：

1. **First Attention Accuracy**：`first_attention.operation` 是否一致。
2. **Strategy Family Jaccard**：把策略映射到粗粒度策略族后计算 Jaccard。
3. **Path Action Similarity**：只保留 `ATTEND/PLAN/REPRESENT/CHECK/BACKTRACK/...` 动作，用 normalized Levenshtein similarity。
4. **Key Event Accuracy**：比较 gold 中可直接由动作定义的 `STUCK / BACKTRACK / CORRECT(self_correct)`。
5. **Completion Accuracy**：归一为 `completed / partial / incomplete` 后比较。

为了总体观察，额外使用一个**仅用于本 pilot 的诊断性 composite**：五项等权平均。它不是经过验证的正式科研指标。

`final_correct` 和 `hint_needed` 没有纳入综合评分：当前 gold 中很多结果属于 `uncertain formula / logical gap / pending review`，且 B 组没有统一的 hint gold。

## 3. 四组公平比较：P05 + P07，共 6 条

| Group | First attention | Strategy | Path | Events | Completion | Composite | Confidence-weighted |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| G0 | 33.3% | 27.8% | 32.4% | 55.6% | 33.3% | **36.5%** | **44.6%** |
| G1 | 83.3% | 47.2% | 37.4% | 55.6% | 50.0% | **54.7%** | **58.8%** |
| G2 | 50.0% | 45.8% | 29.3% | 50.0% | 16.7% | **38.4%** | **45.1%** |
| G3 | 83.3% | 36.1% | 37.2% | 55.6% | 66.7% | **55.8%** | **59.7%** |

### 主要观察

- G3 composite 最高：**55.8%**。
- G1 非常接近：**54.7%**。
- G2：38.4%。
- G0：36.5%。

按 gold trace confidence 加权后：G3=59.7%，G1=58.8%。两者差距仍只有约 0.9 个百分点。

因此当前更合适的描述是：

**G3 ≈ G1 > G2 ≈ G0**

当前最稳定的正向信号不是“retrieval 一定有用”，而是：**加入当前学生 A 组历史后，预测明显改善。**

## 4. 各指标解读

### 4.1 First Attention

- G0：33.3%
- G1：**83.3%**
- G2：50.0%
- G3：**83.3%**

A 组历史对“学生看到新题后最先关注什么”非常有价值，这是当前最强的个性化信号。

### 4.2 Strategy

- G0：27.8%
- G1：**47.2%**
- G2：45.8%
- G3：36.1%

策略相似度上反而是 G1 最好。说明当前 retrieval 有时会把预测拉向“历史学生常见解法”，覆盖当前学生自己的策略偏好。

### 4.3 Path

- G0：32.4%
- G1：37.4%
- G2：29.3%
- G3：37.2%

G1 与 G3 基本持平，说明当前 retrieval 没有稳定提升 reasoning action sequence。

### 4.4 Completion

- G0：33.3%
- G1：50.0%
- G2：16.7%
- G3：**66.7%**

G3 在 completion 上最好，说明“个人历史 + 题目历史难度”组合起来，可能更适合判断最终是完成、部分完成还是未完成。

## 5. 按题目比较

| Question | G0 | G1 | G2 | G3 |
| --- | ---: | ---: | ---: | ---: |
| B1 | 46.7% | 54.8% | 46.7% | 63.3% |
| B2 | 25.2% | 66.0% | 25.1% | 64.0% |
| B3 | 37.5% | 43.3% | 43.3% | 40.0% |

### B1

B1 的标准结构比较明显，question-only 本身就能猜到“坐标选择 + 正方形按边长枚举”。G3 的真正收益主要来自更好地预测 P07 的试探、回退和部分完成，而不是知道标准解。

### B2

B2 是当前最能体现个体差异的一题。P05 会多次尝试、回退和重构；P07 只可靠观察到“球入盒”表示。G1/G3 明显优于 G0/G2。

这说明 B2 很适合作为 personalized trace prediction 的测试题。

### B3

B3 暴露出当前预测器最大的系统性问题：**normative-solution bias（标准解偏置）**。

P05 的真实轨迹是：

```text
鸽巢 → 二倍关系 → (k,2k)配对 → 检查 → 带逻辑缺口作答
```

但 G0/G1/G2/G3 都不同程度预测成：

```text
2^k × odd part → 奇数部分分类 → 标准鸽巢证明
```

也就是说模型更容易生成“这题应该怎么做”，而不是“这个学生实际上会怎么做”。

## 6. 逐条诊断

| Student | Q | Gold 简述 | 主要比较 | 较好条件 |
| --- | --- | --- | --- | --- |
| P05 | B1 | 坐标选择→边长枚举；最后只保留求和。 | G0/G1/G2都抓住主策略；G3额外多预测CHECK/self-correct。 | G0/G2 |
| P05 | B2 | 题意犹豫→六门全用→回退→递推→再回退→格路表示。 | G1最接近真实多次尝试；G3抓到犹豫/回退，但后半段偏向有序队伍；G2误判为卡住。 | G1 |
| P05 | B3 | 鸽巢→二倍配对→检查→有缺口作答。 | 四组均被标准 odd-part 解吸引，均高估策略升级。 | G1/G2/G3并列但都有关键偏差 |
| P07 | B1 | 80点→点对→左下角→回退→小规模→枚举，部分完成。 | G3最好捕捉试探+回退+部分完成；G0/G2过于平滑。 | G3 |
| P07 | B2 | 只可靠看到球入盒表示，未完成。 | G1/G3预测 occupancy 后卡住，明显比G0标准编码更像。 | G1/G3 |
| P07 | B3 | 归纳法→倍数对→不确定分组→n=2检查，未完成。 | G1保留induction候选；G3被retrieval拉向pigeonhole，反而丢失真实第一策略。 | G1 |

## 7. 每条 trace 的 composite

| Student | Question | G0 | G1 | G2 | G3 |
| --- | --- | ---: | ---: | ---: | ---: |
| P05 | B1 | 73.3% | 66.7% | 73.3% | 64.8% |
| P05 | B2 | 41.3% | 65.3% | 30.7% | 61.3% |
| P05 | B3 | 63.3% | 70.0% | 70.0% | 70.0% |
| P07 | B1 | 20.0% | 42.9% | 20.0% | 61.9% |
| P07 | B2 | 9.2% | 66.7% | 19.5% | 66.7% |
| P07 | B3 | 11.7% | 16.7% | 16.7% | 10.0% |

## 8. G0 vs G2：加入 P06 后的 9 条扩展比较

| Group | First attention | Strategy | Path | Events | Completion | Composite | Confidence-weighted |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| G0 | 33.3% | 29.6% | 34.7% | 55.6% | 44.4% | **39.5%** | **45.7%** |
| G2 | 55.6% | 50.9% | 30.7% | 51.9% | 22.2% | **42.2%** | **46.7%** |

G2 总 composite 只比 G0 高约 2.7 个百分点，说明当前“同题 + Top-3 confidence”的 retrieval 本身只有弱增益。

### P06 三题

| Question | G0 | G2 |
| --- | ---: | ---: |
| B1 | 75.2% | 75.2% |
| B2 | 5.0% | 59.0% |
| B3 | 56.7% | 15.7% |

P06-B2 中 retrieval 明显有帮助，因为历史 B2 也普遍出现 occupancy / 分情况 / 卡住。

P06-B3 中 retrieval 反而伤害很大：P06 恰好是少数真正走到 odd-part 分类并完成的人，但 leave-one-out 后历史库里剩下的 P05/P03/P07 大多是不完整的 pairing / pigeonhole 轨迹，因此 retrieval 把预测拉错了。

这揭示了另一个问题：**small-corpus retrieval instability**。历史库太小时，多数模式不一定适合当前学生。

## 9. 当前最重要的三个结论

### 结论 1：A 组个体历史有明显预测价值

G0 composite = 36.5%，G1 = 54.7%，提升约 18.2 个百分点。

First attention 从 33.3% 提升到 83.3%。

因此当前 pilot 最支持的是：**few-shot student history helps predict how the same student approaches a new item**。

### 结论 2：G3 目前只略高于 G1

G3 composite = 55.8%，G1 = 54.7%，差距约 1.1 个百分点。

这个差距在 n=6 时完全不足以说明 G3 明显优于 G1。更准确的表述是：G3 在 completion 上有一些优势，但 retrieval 也会覆盖个体策略。

### 结论 3：标准解偏置是当前最大误差来源

模型常常把真实学生的错误/不完整路径“升级”为更干净的标准解。未来 prompt 应明确：目标不是解题，而是模仿该学生下一步最可能的 reasoning behavior。

## 10. 下一轮实验建议

1. **保留 G0/G1/G2/G3 四组设计。**
2. 主比较优先级：`G1-G0`，其次 `G3-G1`，再看 `G2-G0`。
3. Retrieval 不要继续只用“同题 + trace confidence Top-k”。
4. 应改成：先比较当前学生 A trace 与历史学生 A trace 的相似度，再取最相似学生对应的 B trace。

也就是：

```text
当前学生 A
→ 检索 A-side behavior 最相似的历史学生
→ 取这些历史学生的 A→B paired cases
→ 预测当前学生 B
```

5. 至少补到 10–20 个 paired students，再做 participant-level bootstrap / paired permutation test。
6. Gold 统一补 `stuck/backtrack/self_correct/hint_used/completion/final_correct`，避免后续人工解释。

## 11. 一句话结论

**这批小样本已经出现了“当前学生自己的 A 组 reasoning trace 能改善 B 组行为预测”的明显信号；但当前 retrieval 只提供很小且不稳定的额外收益。下一步真正值得验证的是 A-side personalized retrieval，而不是继续堆同题 B 轨迹。**
