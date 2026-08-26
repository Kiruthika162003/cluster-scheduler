from __future__ import annotations

import pytest

from fleet.errors import Invalid
from fleet.patchcompliance import Advisory, ComplianceTracker


def fleet_of_versions() -> ComplianceTracker:
    tracker = ComplianceTracker()
    for number in range(3):
        tracker.node_runs(f"n{number}", "v1.2")
    tracker.node_runs("n3", "v1.3")
    tracker.publish(
        Advisory(
            name="CVE-1",
            severity="critical",
            affects=("v1.1", "v1.2"),
            published=100,
        )
    )
    return tracker


class TestExposure:
    def test_exposure_names_the_affected_nodes(self):
        tracker = fleet_of_versions()
        assert tracker.exposed_nodes("CVE-1") == ["n0", "n1", "n2"]

    def test_node_ticks_multiply_nodes_by_time_known(self):
        tracker = fleet_of_versions()
        assert tracker.exposure_node_ticks("CVE-1", now=200) == 300

    def test_patching_stops_the_meter(self):
        tracker = fleet_of_versions()
        tracker.node_runs("n0", "v1.3")
        tracker.node_runs("n1", "v1.3")
        assert tracker.exposure_node_ticks("CVE-1", now=200) == 100

    def test_the_unpublished_are_refused(self):
        with pytest.raises(Invalid):
            fleet_of_versions().exposed_nodes("CVE-9")

    def test_double_publication_is_refused(self):
        tracker = fleet_of_versions()
        with pytest.raises(Invalid):
            tracker.publish(
                Advisory(
                    name="CVE-1",
                    severity="high",
                    affects=("v1.2",),
                    published=1,
                )
            )

    def test_an_advisory_that_affects_nothing_is_refused(self):
        with pytest.raises(Invalid, match="why file it"):
            Advisory(name="CVE-0", severity="high", affects=(), published=0)


class TestTheFuse:
    def test_inside_the_fuse_nobody_is_overdue(self):
        tracker = fleet_of_versions()
        assert tracker.past_the_fuse(now=110) == []

    def test_past_the_fuse_every_node_is_named(self):
        tracker = fleet_of_versions()
        rows = tracker.past_the_fuse(now=120)
        assert rows == [("n0", "CVE-1", 6), ("n1", "CVE-1", 6), ("n2", "CVE-1", 6)]

    def test_severity_sets_the_fuse_length(self):
        tracker = fleet_of_versions()
        tracker.publish(
            Advisory(
                name="CVE-2",
                severity="medium",
                affects=("v1.3",),
                published=100,
            )
        )
        rows = tracker.past_the_fuse(now=120)
        assert all(name == "CVE-1" for _, name, _ in rows)

    def test_the_report_reads_both_meters(self):
        tracker = fleet_of_versions()
        page = tracker.report(now=120)
        assert "CVE-1 (critical): 3 nodes, 60 node-ticks of exposure" in page
        assert "3 node(s) past the fuse:" in page
        assert "n0 vs CVE-1: 6 past deadline" in page

    def test_an_empty_file_says_so(self):
        assert ComplianceTracker().report(now=0) == "no advisories on file"
