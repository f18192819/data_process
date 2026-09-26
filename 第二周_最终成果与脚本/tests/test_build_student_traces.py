from __future__ import annotations

import importlib.util
import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "build_student_traces.py"
SPEC = importlib.util.spec_from_file_location("build_student_traces", SCRIPT)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(MODULE)


class TracePipelineTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.bank = json.loads((ROOT / "configs" / "question_bank_selected.json").read_text(encoding="utf-8"))
        cls.annotations = json.loads((ROOT / "configs" / "reviewed_trace_annotations.json").read_text(encoding="utf-8"))
        for extra in sorted((ROOT / "configs").glob("reviewed_trace_annotations_*.json")):
            cls.annotations["participants"].update(json.loads(extra.read_text(encoding="utf-8"))["participants"])

    def test_question_bank_has_six_complete_groups(self):
        self.assertEqual(len(self.bank["groups"]), 6)
        self.assertTrue(all(len(group["questions"]) == 3 for group in self.bank["groups"]))
        ids = [q["question_id"] for g in self.bank["groups"] for q in g["questions"]]
        self.assertEqual(len(ids), 18)
        self.assertEqual(len(set(ids)), 18)

    def test_p05_joint_alignment_sanity(self):
        p05 = self.annotations["participants"]["P05"]
        self.assertEqual(p05["assigned_group"], "TRIG_A")
        self.assertGreaterEqual(p05["alignment_confidence"], 0.9)
        self.assertEqual([s["question_id"] for s in p05["segments"]], ["TRIG_A1", "TRIG_A2", "TRIG_A3"])
        self.assertEqual([s["slot"] for s in p05["segments"]], [1, 2, 3])

    def test_observed_trace_schema_and_evidence(self):
        for trace in self.annotations["participants"]["P05"]["traces"]:
            MODULE.validate_trace(trace)
            self.assertTrue(trace["steps"])
            self.assertTrue(all(step["status"] != "ANALYST_INFERENCE" for step in trace["steps"]))

    def test_variants_exclude_unattempted_questions(self):
        traces = []
        for participant_id, participant in self.annotations["participants"].items():
            for trace in participant["traces"]:
                traces.append({**MODULE.expand_trace(trace), "participant_id": participant_id})
        variants = MODULE.build_variants(self.bank, traces)
        self.assertEqual(len(variants), 12)
        self.assertTrue(all(v["n_participants"] > 0 for v in variants))
        self.assertFalse({"TRIG_B1", "TRIG_B2", "TRIG_B3", "TRIG_C1", "TRIG_C2", "TRIG_C3"} &
                         {v["question_id"] for v in variants})

    def test_all_eighteen_traces_validate_and_audio_times_are_ordered(self):
        count = 0
        for participant_id, participant in self.annotations["participants"].items():
            self.assertEqual([s["slot"] for s in participant["segments"]], [1, 2, 3])
            for compact in participant["traces"]:
                trace = MODULE.expand_trace(compact)
                MODULE.validate_trace(trace)
                count += 1
                if participant_id in {"P01", "P02", "P03", "P04"}:
                    starts = [step["start_sec"] for step in trace["steps"]]
                    self.assertEqual(starts, sorted(starts), trace["trace_id"])
                    self.assertTrue(all(step["end_sec"] is not None for step in trace["steps"]))
        self.assertEqual(count, 18)

    def test_p06_preserves_correction_chain_and_written_evidence(self):
        p06 = self.annotations["participants"]["P06"]
        self.assertEqual(p06["assigned_group"], "TRIG_A")
        a1 = MODULE.expand_trace(p06["traces"][0])
        self.assertEqual(
            [step["action_type"] for step in a1["steps"]],
            ["HESITATE", "RECALL", "ERROR", "BACKTRACK", "ATTEND", "RECALL", "CORRECT"],
        )
        self.assertTrue(all(step["status"] in {"WRITTEN_OBSERVED", "STRONGLY_IMPLIED"} for step in a1["steps"]))
        self.assertFalse(a1["final_answer_observed"])
        a3 = MODULE.expand_trace(p06["traces"][2])
        self.assertGreaterEqual(len(a3["steps"]), 10)

    def test_p02_user_transcript_rebuild_preserves_full_reasoning(self):
        p02 = self.annotations["participants"]["P02"]
        self.assertEqual(p02["source_type"], "user_provided_timestamped_transcript_reviewed_against_audio_asr")
        a1, a2, a3 = [MODULE.expand_trace(trace) for trace in p02["traces"]]
        self.assertEqual([len(a1["steps"]), len(a2["steps"]), len(a3["steps"])], [12, 10, 7])
        self.assertIn("那不对", [step["evidence_text"] for step in a1["steps"]])
        self.assertEqual(a1["steps"][-1]["result"], "(m+n)!-2(m+n-1)!")
        self.assertEqual(
            [step["action_type"] for step in a2["steps"]][4:7],
            ["CHECK", "BACKTRACK", "PLAN"],
        )
        self.assertEqual(a3["steps"][-1]["action_type"], "ANSWER")

    def test_trig_a2_same_strategy_merges_into_one_family(self):
        traces = []
        for participant_id, participant in self.annotations["participants"].items():
            for trace in participant["traces"]:
                traces.append({**MODULE.expand_trace(trace), "participant_id": participant_id})
        variants = MODULE.build_variants(self.bank, traces)
        a2 = next(item for item in variants if item["question_id"] == "TRIG_A2")
        self.assertEqual(a2["n_participants"], 2)
        self.assertEqual(len(a2["trace_families"]), 1)
        self.assertEqual(a2["common_prefix"], ["DERIVE(T=π)"])
        self.assertIn("P05", a2["first_meaningful_divergence"])
        self.assertIn("P06", a2["first_meaningful_divergence"])

    def test_every_report_path_step_has_source_evidence_mapping(self):
        traces = []
        for participant_id, participant in self.annotations["participants"].items():
            for trace in participant["traces"]:
                traces.append({**MODULE.expand_trace(trace), "participant_id": participant_id})
        variants = MODULE.build_variants(self.bank, traces)
        for variant in variants:
            for family in variant["trace_families"]:
                self.assertEqual(len(family["core_steps"]), len(family["core_step_evidence"]))
                self.assertEqual(set(family["participants"]), set(family["participant_paths"]))
                for step in family["core_step_evidence"]:
                    self.assertTrue(step["evidence_text"])
                    self.assertIn(step["status"], MODULE.EVIDENCE_STATUS)
                for participant_steps in family["participant_paths"].values():
                    self.assertTrue(participant_steps)
                    self.assertTrue(all(step["evidence_text"] for step in participant_steps))

    def test_source_inventory_records_directory_zip_difference(self):
        inventory_path = ROOT / "data" / "raw" / "collected_2026_09" / "source_inventory.json"
        if not inventory_path.exists():
            self.skipTest("Private raw source inventory is not included in the public repository")
        inventory = json.loads(
            inventory_path.read_text(encoding="utf-8")
        )
        self.assertEqual(len(inventory["participants"]), 6)
        derived = [
            row["participant_id"]
            for row in inventory["participants"]
            if row["present_in_source_zip"] is False
        ]
        self.assertEqual(inventory["participants_not_in_source_zip"], derived)
        self.assertIn("P06", derived)

    def test_question_report_has_participant_index(self):
        report = (ROOT / "reports" / "by_question_trace_report.md").read_text(encoding="utf-8")
        self.assertIn("## 按被测者索引", report)
        self.assertIn("**P01**：[COMB_A1](#comb_a1), [COMB_A2](#comb_a2), [COMB_A3](#comb_a3)", report)

    def test_normalization_keeps_raw_separate_and_flags_uncertain_math(self):
        raw = "Y=tan X，阿尔FX，阿尔法等于1+2派2贝塔等于1"
        clean, normalizations, uncertain = MODULE.normalize_text(raw)
        self.assertIn("y=tan x", clean)
        self.assertIn("Y=tan X", raw)
        self.assertTrue(normalizations)
        self.assertEqual(len(uncertain), 2)


if __name__ == "__main__":
    unittest.main()
