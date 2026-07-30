"""Week-3 tests: API, approximation fidelity, and cache behavior."""

from __future__ import annotations

import unittest

from commscm.attribution.engines import CachedReplayEstimator, DescendantReplayEstimator, ExactReplayOracle
from commscm.attribution.report import AttributionReport
from commscm.benchmarks.week3_random import build_random_dataset
from commscm.estimators.replay import CachedDescendantReplayEngine, DescendantReplayEngine, FullReplayEngine, fault_marker_outcome
from commscm.eval.localization import kendall_tau, spearman_corr
from commscm.runtime.mechanisms import MechanismRegistry


class Week3Tests(unittest.TestCase):
    def setUp(self) -> None:
        self.traces = build_random_dataset(n_traces=5, n_events=14, seed=101)
        self.oracle = ExactReplayOracle(FullReplayEngine(fault_marker_outcome, MechanismRegistry()))
        self.desc = DescendantReplayEstimator(DescendantReplayEngine(fault_marker_outcome, MechanismRegistry()))
        self.cached_engine = CachedDescendantReplayEngine(fault_marker_outcome, MechanismRegistry())
        self.cached = CachedReplayEstimator(self.cached_engine)

    def test_api_shape(self) -> None:
        report = self.oracle.score(self.traces[0])
        self.assertIsInstance(report, AttributionReport)
        self.assertEqual(report.engine_name, "ExactReplayOracle")
        self.assertEqual(len(report.rows), len(self.traces[0].dag.events))

    def test_descendant_matches_oracle_top1(self) -> None:
        for tr in self.traces:
            a = self.oracle.score(tr)
            b = self.desc.score(tr)
            self.assertEqual(a.predicted_top1, b.predicted_top1)

    def test_cached_matches_oracle_top1(self) -> None:
        for tr in self.traces:
            a = self.oracle.score(tr)
            b = self.cached.score(tr)
            self.assertEqual(a.predicted_top1, b.predicted_top1)

    def test_rank_correlation_perfect_on_deterministic_random_set(self) -> None:
        for tr in self.traces:
            a = self.oracle.score(tr)
            b = self.desc.score(tr)
            ids = [r.event_id for r in a.rows]
            ax = [next(r.delta_y for r in a.rows if r.event_id == i) for i in ids]
            bx = [next(r.delta_y for r in b.rows if r.event_id == i) for i in ids]
            self.assertGreaterEqual(kendall_tau(ax, bx), 0.99)
            self.assertGreaterEqual(spearman_corr(ax, bx), 0.99)

    def test_cache_hits_reduce_repeat_runtime(self) -> None:
        tr = self.traces[0]
        first = self.cached.score(tr)
        second = self.cached.score(tr)
        self.assertLessEqual(second.total_runtime_ms, first.total_runtime_ms)


if __name__ == "__main__":
    unittest.main()
