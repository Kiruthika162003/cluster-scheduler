from __future__ import annotations

from fleet.shadow import ShadowDiff


class TestShadowDiff:
    def test_agreement_counts_and_returns_production(self):
        diff = ShadowDiff()
        told = diff.mirror(5, lambda x: x * 2, lambda x: x * 2)
        assert told == 10
        assert diff.agreed == 1 and diff.compared == 1

    def test_the_caller_always_gets_the_production_answer(self):
        diff = ShadowDiff()
        told = diff.mirror(5, lambda _: "right", lambda _: "wrong")
        assert told == "right"

    def test_disagreements_bucket_by_request_kind(self):
        diff = ShadowDiff()
        diff.mirror(5, lambda _: 1, lambda _: 2)
        diff.mirror("q", lambda _: 1, lambda _: 2)
        assert diff.disagreements == {"int": 1, "str": 1}

    def test_samples_cap_but_counts_do_not(self):
        diff = ShadowDiff(sample_cap=2)
        for number in range(10):
            diff.mirror(number, lambda _: 1, lambda _: 2)
        assert len(diff.samples) == 2
        assert diff.compared - diff.agreed == 10

    def test_the_verdict_promotes_at_the_floor(self):
        diff = ShadowDiff()
        for number in range(1000):
            diff.mirror(number, lambda x: x, lambda x: x)
        assert diff.verdict().startswith("promote")

    def test_an_empty_diff_promotes_vacuously(self):
        assert ShadowDiff().verdict().startswith("promote")
