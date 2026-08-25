from __future__ import annotations

import pytest

from fleet.errors import Invalid
from fleet.skewpolicy import SkewGate, minor_gap, parse


class TestParsing:
    def test_major_minor_parses(self):
        assert parse("1.28") == (1, 28)

    def test_extra_segments_are_refused(self):
        with pytest.raises(Invalid):
            parse("1.28.3")

    def test_words_are_refused(self):
        with pytest.raises(Invalid):
            parse("one.two")

    def test_a_major_gap_is_effectively_infinite(self):
        assert minor_gap("2.0", "1.9") == 10**6


class TestAdmission:
    def test_nodes_inside_the_window_join(self):
        gate = SkewGate(control_plane="1.28")
        for version in ("1.28", "1.27", "1.26"):
            gate.admit_node(f"n-{version}", version)
        assert len(gate.node_versions) == 3

    def test_a_node_too_old_is_refused_with_the_gap(self):
        gate = SkewGate(control_plane="1.28")
        with pytest.raises(Invalid) as caught:
            gate.admit_node("relic", "1.25")
        assert "lags 3 minors" in str(caught.value)

    def test_a_node_from_the_future_is_refused(self):
        gate = SkewGate(control_plane="1.28")
        with pytest.raises(Invalid) as caught:
            gate.admit_node("timetraveller", "1.29")
        assert "ahead of the control plane" in str(caught.value)


class TestControlPlaneUpgrades:
    def joined(self) -> SkewGate:
        gate = SkewGate(control_plane="1.28")
        gate.admit_node("fresh", "1.28")
        gate.admit_node("older", "1.26")
        return gate

    def test_an_upgrade_inside_the_window_lands(self):
        gate = self.joined()
        gate.upgrade_control_plane("1.28")
        assert gate.upgrade_control_plane("1.28") == ["fresh", "older"]

    def test_an_orphaning_upgrade_is_refused_naming_everyone(self):
        gate = self.joined()
        with pytest.raises(Invalid) as caught:
            gate.upgrade_control_plane("1.29")
        assert "older at 1.26" in str(caught.value)
        assert gate.control_plane == "1.28"

    def test_upgrading_the_node_first_unblocks_the_plane(self):
        gate = self.joined()
        gate.node_versions["older"] = "1.27"
        gate.upgrade_control_plane("1.29")
        assert gate.control_plane == "1.29"

    def test_laggards_are_the_nodes_at_the_edge(self):
        gate = self.joined()
        assert gate.laggards() == ["older"]
