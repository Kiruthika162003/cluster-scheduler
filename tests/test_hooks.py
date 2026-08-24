from __future__ import annotations

import pytest

from fleet.control.hooks import (
    Chain,
    default_labels,
    minimum_resources,
    refuse_label,
    require_label,
)
from fleet.errors import Invalid
from fleet.objects import Resources, TaskSpec


def spec(**kw) -> TaskSpec:
    kw.setdefault("name", "t")
    kw.setdefault("needs", Resources(cpu=50, memory=50))
    return TaskSpec(**kw)


class TestMutators:
    def test_default_labels_fill_only_the_missing(self):
        hook = default_labels(team="core", tier="web")
        shaped = hook(spec(labels=(("team", "search"),)))
        held = shaped.label_map()
        assert held == {"team": "search", "tier": "web"}

    def test_minimum_resources_raise_the_floor(self):
        hook = minimum_resources(cpu=100, memory=200)
        shaped = hook(spec())
        assert shaped.needs == Resources(cpu=100, memory=200)

    def test_a_generous_ask_is_untouched(self):
        hook = minimum_resources(cpu=100, memory=100)
        rich = spec(needs=Resources(cpu=500, memory=500))
        assert hook(rich) is rich


class TestValidators:
    def test_refuse_label_names_the_offender(self):
        hook = refuse_label("privileged", "true")
        assert hook(spec(labels=(("privileged", "true"),))) is not None
        assert hook(spec()) is None

    def test_require_label_demands_presence(self):
        hook = require_label("team")
        assert hook(spec()) is not None
        assert hook(spec(labels=(("team", "x"),))) is None


class TestChainOrdering:
    def built(self) -> Chain:
        chain = Chain()
        chain.mutate_with("defaults", default_labels(team="core"))
        chain.validate_with("need-team", require_label("team"))
        chain.validate_with("no-priv", refuse_label("privileged", "true"))
        return chain

    def test_validators_judge_the_mutated_shape(self):
        chain = self.built()
        shaped = chain.admit(spec())
        assert shaped.label_map()["team"] == "core"

    def test_a_refusal_raises_with_the_hook_name(self):
        chain = self.built()
        with pytest.raises(Invalid) as caught:
            chain.admit(spec(labels=(("privileged", "true"),)))
        assert "no-priv" in str(caught.value)
        assert chain.refusals == 1

    def test_the_trace_tells_the_story(self):
        chain = self.built()
        chain.admit(spec())
        assert chain.trace == ["defaults reshaped t", "admitted t"]

    def test_an_untouched_admission_traces_once(self):
        chain = Chain()
        chain.admit(spec())
        assert chain.trace == ["admitted t"]

    def test_mutators_run_in_registration_order(self):
        chain = Chain()
        chain.mutate_with("first", default_labels(owner="first"))
        chain.mutate_with("second", default_labels(owner="second"))
        shaped = chain.admit(spec())
        assert shaped.label_map()["owner"] == "first"
