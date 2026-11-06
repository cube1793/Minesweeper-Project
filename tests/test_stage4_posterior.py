from dataclasses import FrozenInstanceError, replace
from math import comb
import unittest
from unittest.mock import patch

import stage4_posterior as posterior
from stage4_posterior import PosteriorRequest, SamplerLimits, sample_posterior
from tests import stage4_policy_oracle as oracle


H, F = -2, -3


class PosteriorTests(unittest.TestCase):
    def test_all_ranks_match_independent_raw_masks(self):
        fixtures = [
            (((H,),), 0), (((H,),), 1), (((0,),), 0),
            (((H, H, H, H),), 2), (((H, 1, H),), 1),
            (((H, 1, H, 1, H, H, H),), 2),
            (((H, 1, H, 1, H, H, H),), 3),
            (((H, 1, H, H, H, 1, H),), 2),
            (((H, 1, H), (H, 1, H)), 1),
            (((0, H, H), (H, H, H)), 1),
        ]
        for index, (grid, mines) in enumerate(fixtures):
            with self.subTest(index=index):
                expected = oracle.raw_worlds(grid, mines)
                result = sample_posterior(PosteriorRequest(grid, mines, samples=64))
                self.assertEqual(result.status, "COMPLETE")
                self.assertEqual(result.total_worlds, len(expected))
                self.assertEqual(result.sampling_kind, "SMALL_POSTERIOR_ENUMERATED")
                actual = [frozenset(sample.mines) for sample in result.samples]
                self.assertEqual(len(set(actual)), len(actual))
                self.assertEqual(set(actual), set(expected))
                oracle.EMIT("rank_oracle", {"fixture": index, "grid": grid, "num_mines": mines,
                                            "oracle": [sorted(w) for w in expected], "actual": result})

    def test_d3_mine_count_weights_and_order(self):
        grid = ((H, 1, H, 1, H, H, H),)
        result = sample_posterior(PosteriorRequest(grid, 2), ranks=(0, 1, 2))
        self.assertEqual([sample.mines for sample in result.samples],
                         [((2, 0), (5, 0)), ((2, 0), (6, 0)), ((0, 0), (4, 0))])
        self.assertEqual(result.diagnostics.histograms, (((1, 1), (2, 1)),))
        self.assertEqual(result.total_worlds, 3)

    def test_physical_flags_preserve_distribution_and_seed(self):
        grid = ((H, 1, H, 1, H, H, H),)
        flagged = ((F, 1, F, 1, H, F, H),)
        a = sample_posterior(PosteriorRequest(grid, 2, planning_seed="public", samples=2))
        b = sample_posterior(PosteriorRequest(flagged, 2, planning_seed="public", samples=2))
        self.assertEqual(a.samples, b.samples)
        self.assertEqual(a.seed_id, b.seed_id)
        self.assertEqual(a.total_worlds, b.total_worlds)

    def test_large_integer_rank_and_floating_combinations(self):
        grid = (tuple(H for _ in range(64)),)
        total = comb(64, 32)
        self.assertGreater(total, 2 ** 53)
        result = sample_posterior(PosteriorRequest(grid, 32), ranks=(0, total - 1, 2 ** 53 + 1))
        self.assertEqual(result.total_worlds, total)
        self.assertEqual(result.samples[0].mines, tuple((x, 0) for x in range(32)))
        self.assertEqual(result.samples[1].mines, tuple((x, 0) for x in range(32, 64)))
        for sample in result.samples:
            self.assertTrue(oracle.consistent(grid, 32, sample.mines))
        self.assertEqual(int(result.to_dict()["total_worlds"]), total)

    def test_with_replacement_keeps_duplicate_multiplicity(self):
        class RepeatedIntegerRandom:
            def __init__(self, seed):
                pass

            def randrange(self, stop):
                return stop - 1

        with patch.object(posterior, "Random", RepeatedIntegerRandom):
            result = sample_posterior(PosteriorRequest(((H, H, H, H, H),), 2, samples=4))
        self.assertEqual(result.sampling_kind, "WITH_REPLACEMENT")
        self.assertEqual(len(result.samples), 4)
        self.assertEqual(result.unique_layout_count, 1)
        self.assertEqual(len({sample.rank for sample in result.samples}), 1)

    def test_cutoff_and_cancel_inside_each_computation_phase(self):
        request = PosteriorRequest(((H, 1, H, 1, H, H, H),), 2)
        original = posterior._Meter.tick
        for stage in ("histogram", "dp", "comb", "unrank", "recovery"):
            reached = []

            def tick(meter, current):
                if current == stage:
                    reached.append(current)
                original(meter, current)

            with patch.object(posterior._Meter, "tick", tick):
                result = sample_posterior(request, cancelled=lambda: bool(reached))
            self.assertTrue(reached, stage)
            self.assertEqual(result.status, "CANCELLED", stage)
            self.assertEqual(result.samples, (), stage)
        for cap in (0, 10, 30):
            result = sample_posterior(replace(request, limits=SamplerLimits(max_work=cap)))
            self.assertEqual(result.status, "INSUFFICIENT")
            self.assertLessEqual(result.diagnostics.work, cap)
            self.assertFalse(result.samples)

    def test_input_errors_and_atomic_failures(self):
        for grid, mines in ((((2, H),), 1), (((H, 0, H),), 1)):
            result = sample_posterior(PosteriorRequest(grid, mines))
            self.assertEqual(result.status, "INCONSISTENT_INPUT")
            self.assertEqual(result.total_worlds, 0)
            self.assertFalse(result.samples)
        request = PosteriorRequest(((H, H),), 1)
        self.assertEqual(sample_posterior(request, cancelled=lambda: "yes").status, "ERROR")
        self.assertEqual(sample_posterior(replace(request, limits=SamplerLimits(max_seconds=0))).status, "INSUFFICIENT")
        self.assertEqual(sample_posterior(request, ranks=(2,)).status, "ERROR")
        self.assertEqual(sample_posterior(replace(request, samples=0)).reason, "NO_SAMPLES")
        self.assertEqual(sample_posterior(replace(request, limits=SamplerLimits(max_cells=1))).status, "UNSUPPORTED")
        with self.assertRaises((FrozenInstanceError, AttributeError)):
            request.samples = 1
        with self.assertRaises((ValueError, TypeError)):
            PosteriorRequest(((True,),), 0)
