from __future__ import annotations

import pytest

from fleet.apiversions import CONVERTERS, Gateway
from fleet.errors import Invalid
from fleet.objects import Resources, TaskSpec


def rich_spec() -> TaskSpec:
    return TaskSpec(
        name="web-0",
        needs=Resources(cpu=200, memory=300),
        labels=(("app", "web"),),
        namespace="shop",
        priority=1500,
        tolerates=("gpu",),
    )


class TestRoundTrips:
    @pytest.mark.parametrize("version", sorted(CONVERTERS))
    def test_every_version_round_trips_its_own_fields(self, version):
        serialize, deserialize = CONVERTERS[version]
        spec = rich_spec()
        back = deserialize(serialize(spec))
        again = deserialize(serialize(back))
        assert back == again

    def test_v2_round_trips_everything(self):
        gateway = Gateway()
        data = gateway.read(rich_spec(), "v2")
        assert gateway.write(data) == rich_spec()

    def test_v1_keeps_the_shared_fields(self):
        gateway = Gateway()
        back = gateway.write(gateway.read(rich_spec(), "v1"))
        assert back.name == "web-0"
        assert back.needs == Resources(cpu=200, memory=300)
        assert back.label_map() == {"app": "web"}


class TestDrops:
    def test_v1_drops_are_recorded_by_field(self):
        gateway = Gateway()
        gateway.read(rich_spec(), "v1")
        assert gateway.drops == [
            "web-0: v1 cannot carry namespace",
            "web-0: v1 cannot carry priority",
            "web-0: v1 cannot carry tolerates",
        ]

    def test_a_plain_spec_drops_nothing(self):
        gateway = Gateway()
        plain = TaskSpec(name="plain", needs=Resources(cpu=1, memory=1))
        gateway.read(plain, "v1")
        assert gateway.drops == []

    def test_unknown_versions_are_refused_both_ways(self):
        gateway = Gateway()
        with pytest.raises(Invalid):
            gateway.read(rich_spec(), "v9")
        with pytest.raises(Invalid):
            gateway.write({"version": "v9"})
