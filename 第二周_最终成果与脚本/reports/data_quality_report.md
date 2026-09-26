# Data Quality Report

Generated: `2026-09-20T17:08:20.268805+00:00`

## Raw audit

- Participant-level source files: 6（4 audio + 2 text）
- Source ZIP recorded: yes
- Source ZIP entries: 5
- Sources present in the directory but absent from the original ZIP: P05, P06.
- The original ZIP is preserved unchanged; post-ZIP additions are tracked as separate raw sources.
- Total audio duration: 2205.148 seconds
- Source files were hashed and were not modified.

### Audio duration

- P01: 366.037 s
- P02: 750.19 s
- P03: 634.137 s
- P04: 454.784 s

## Transcription status

- P01: success
- P02: success
- P03: success
- P04: success
- P05: success
- P06: success

- ASR boilerplate hallucination detected and marked for: P01, P02, P03, P04.
- P02 trace evidence was rebuilt from the user-provided timestamped transcript `P02.user_provided_original.txt`; step times are paragraph-level approximate alignments, the audio remains the raw source, and off-task game/chat crosstalk is excluded from observed steps.
- P05 is marked `user_provided_text`; P06 is `user_provided_curated_multimodal_text`; neither is represented as audio ASR.

## Segmentation and alignment

- P05: group `TRIG_A` confidence 0.99; boundary confidences Q1=0.90, Q2=0.90, Q3=0.82
- P01: group `COMB_A` confidence 0.99; boundary confidences Q1=0.95, Q2=0.93, Q3=0.97
- P02: group `COMB_A` confidence 1.00; boundary confidences Q1=0.99, Q2=0.96, Q3=0.97
- P03: group `COMB_B` confidence 0.99; boundary confidences Q1=0.92, Q2=0.94, Q3=0.96
- P04: group `COMB_C` confidence 0.99; boundary confidences Q1=0.95, Q2=0.97, Q3=0.98
- P06: group `TRIG_A` confidence 1.00; boundary confidences Q1=1.00, Q2=1.00, Q3=1.00

## Trace extraction

- Observed traces extracted: 18
- Low-confidence traces (<0.75): 3
- Questions retained in trace outputs: 12 / 18
- Questions omitted because no participant attempted them: 6
- Omitted: TRIG_B1, TRIG_B2, TRIG_B3, TRIG_C1, TRIG_C2, TRIG_C3

## Manual review

- Queue rows: 46
- Transcription blockers: none; all 6 participant sources were processed.
- P01–P04 contain marked ASR hallucination/uncertainty spans; every low-confidence step remains queued for audio review.
- P05 and P06 have no audio-relative timestamps; their compiled-text boundaries remain explicit confidence-bearing records.
- The third-person P05 note is retained as secondary evidence and excluded from observed steps.
