"""Multi-fault exact-replay localization tests."""

from __future__ import annotations

import unittest

from commscm.attribution.exact import attribute_exact
from commscm.benchmarks.causal_comm_bench import build_multi_fault_dataset
from commscm.eval.localization import aggregate_multi_fault, ndcg_at_k, recall_at_k
from commscm.experiments.week2_multi_fault import build_graded_engine


class MultiFaultTests(unittest.TestCase):
    def test_both_gold_faults_in_top2(self) -> None:
        engine = build_graded_engine()
        reports = []
        golds = []
        for case in build_multi_fault_dataset():
            report = attribute_exact(case.trace, engine)
            reports.append(report)
            gold = set(case.true_event_ids)
            golds.append(gold)
            ranked = [r.event_id for r in report.rows]
            self.assertEqual(recall_at_k(ranked, gold, 2), 1.0, msg=case.case_id)
            self.assertGreaterEqual(ndcg_at_k(ranked, gold, 2), 1.0 - 1e-9)
            # Each gold should get positive ΔY under graded outcome
            for eid in gold:
                row = next(r for r in report.rows if r.event_id == eid)
                self.assertGreater(row.delta_y, 0.0, msg=f"{case.case_id}:{eid}")

        metrics = aggregate_multi_fault(reports, golds)
        self.assertEqual(metrics.recall_at_2, 1.0)
        self.assertEqual(metrics.ndcg_at_2, 1.0)
        self.assertGreater(metrics.mean_kendall_tau, 0.5)


if __name__ == "__main__":
    unittest.main()
