# Trace Pilot Run

Generated: `2026-09-20T17:08:20.268805+00:00`

## Acceptance answers

1. Group alignment: P01 → `COMB_A` (0.99)；P02 → `COMB_A` (1.00)；P03 → `COMB_B` (0.99)；P04 → `COMB_C` (0.99)；P05 → `TRIG_A` (0.99)；P06 → `TRIG_A` (1.00).
2. Three-question split: P01 → `COMB_A1`, `COMB_A2`, `COMB_A3`；P02 → `COMB_A1`, `COMB_A2`, `COMB_A3`；P03 → `COMB_B1`, `COMB_B2`, `COMB_B3`；P04 → `COMB_C1`, `COMB_C2`, `COMB_C3`；P05 → `TRIG_A1`, `TRIG_A2`, `TRIG_A3`；P06 → `TRIG_A1`, `TRIG_A2`, `TRIG_A3`.
3. First attention: P01: Q1 PLAN(C1, 0.94)；Q2 REPRESENT(S1,S3, 0.91)；Q3 ATTEND(S1, 0.98) | P02: Q1 ATTEND(C1, 0.99)；Q2 REPRESENT(S1,S2, 0.99)；Q3 ATTEND(S1,S3, 0.94) | P03: Q1 CALCULATE(G2, 0.58)；Q2 ATTEND(S1,S2, 0.93)；Q3 STUCK(无可确认signal, 0.94) | P04: Q1 ATTEND(S1,G1, 0.97)；Q2 ATTEND(S2, 0.98)；Q3 ATTEND(S2, 0.98) | P05: Q1 RECALL(S3, 0.94)；Q2 DERIVE(无可确认signal, 0.58)；Q3 STUCK(无可确认signal, 0.99) | P06: Q1 HESITATE(G, 0.99)；Q2 DERIVE(无可确认signal, 0.72)；Q3 TRANSFORM(S1,G1, 0.96).
4. Signatures are listed in `participant_trace_summary.md` and the JSONL output.
5. Current observed family counts: TRIG_A1=2；TRIG_A2=1；TRIG_A3=2；COMB_A1=2；COMB_A2=2；COMB_A3=2；COMB_B1=1；COMB_B2=1；COMB_B3=1；COMB_C1=1；COMB_C2=1；COMB_C3=1；另有 6 道无人作答题已从 trace 输出和逐题报告中移除。
6. Same-question divergence: TRIG_A1 中 P05 直接用周期性构造，P06 先误用锐角单调性再自我修正；TRIG_A2 中 P05/P06 属于同一‘先得周期再给 ω’family，但外显步骤长度不同；TRIG_A3 中 P05 无法切入，P06 完成正弦定理—余弦定理—面积路线。COMB_A1–A3 的 P01/P02 分叉保持原报告结论。
7. Data-supported revisions/events: P01 在 COMB_A1 放弃第二条插入路线；P02 在 COMB_A1 明确否定首轮间隔计数并重算，在 COMB_A2 对 Catalan 套用进行自检后改用总路径减反射坏路径；P03 在 COMB_B3 明确卡住；P04 在 COMB_C1 自我修正后停止求和；P05 在 TRIG_A3 报告不会做和忘记公式；P06 在 TRIG_A1 出现可观察的误判—回退—纠正。没有把仅凭最终答案推测的错误标为 ERROR。
8. Analyst inference 共 10 条，均在独立字段和报告小节中展示，没有混入 observed steps。
9. Manual review queue contains 46 rows: ASR_UNCERTAIN=4，CORRECTNESS_UNCERTAIN=16，MATH_TERM_UNCERTAIN=2，QUESTION_BOUNDARY_UNCERTAIN=1，RAW_LAYOUT_DIFFERENCE=2，SOURCE_EVIDENCE_UNAVAILABLE=1，TRACE_STEP_UNCERTAIN=20。
10. 当前样本支持一个受限描述：P01/P02 与 P05/P06 分别在相同题目上出现了可观察的路径差异；样本不足以外推这些差异的总体分布或穷尽题目解法。

## Primary output

- `reports/by_question_trace_report.md`
- `reports/trace_granularity_audit.md`

## Reproduce

```powershell
python scripts/run_full_pipeline.py
# Or run each stage separately:
python scripts/transcribe_groq_batch.py --input-dir '收集数据结果' --output-dir 'data/interim/transcripts_raw'
python scripts/transcribe_question_clips_groq.py --input-dir '收集数据结果' --clip-dir 'data/interim/asr_clips' --output-dir 'data/interim/transcripts_raw_resegmented'
python scripts/build_student_traces.py --input '收集数据结果.zip' --question-bank 'configs/question_bank_selected.json' --output 'data/processed/trace_pilot'
python -m unittest discover -s tests -v
```

The transcription command requires `GROQ_API_KEY` in the process environment. No key is read from files or written to outputs.
