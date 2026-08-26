from __future__ import annotations

import pytest

from fleet.errors import Invalid
from fleet.tracing import Trace


def pass_trace() -> Trace:
    trace = Trace()
    trace.open("pass", 0)
    trace.open("task web-0", 0)
    trace.open("filters", 0)
    trace.note("3 nodes rejected by fits")
    trace.close("filters", 12)
    trace.open("scoring", 12)
    trace.close("scoring", 15)
    trace.close("task web-0", 15)
    trace.open("task api-0", 15)
    trace.open("filters", 15)
    trace.close("filters", 17)
    trace.close("task api-0", 17)
    trace.close("pass", 18)
    return trace


class TestSpans:
    def test_nesting_follows_the_stack(self):
        trace = pass_trace()
        assert [child.name for child in trace.root.children] == [
            "task web-0",
            "task api-0",
        ]

    def test_durations_are_close_minus_open(self):
        trace = pass_trace()
        assert trace.root.duration() == 18
        assert trace.root.children[0].children[0].duration() == 12

    def test_closing_out_of_order_is_refused_by_name(self):
        trace = Trace()
        trace.open("outer", 0)
        trace.open("inner", 1)
        with pytest.raises(Invalid, match="inner is innermost"):
            trace.close("outer", 2)

    def test_a_second_root_is_refused(self):
        trace = Trace()
        trace.open("first", 0)
        trace.close("first", 1)
        with pytest.raises(Invalid):
            trace.open("second", 2)

    def test_notes_need_an_open_span(self):
        with pytest.raises(Invalid):
            Trace().note("orphan")


class TestCriticalPath:
    def test_the_path_walks_the_longest_child(self):
        trace = pass_trace()
        assert trace.critical_path() == ["pass", "task web-0", "filters"]

    def test_an_empty_trace_has_no_path(self):
        with pytest.raises(Invalid):
            Trace().critical_path()

    def test_open_children_are_not_on_the_path(self):
        trace = Trace()
        trace.open("pass", 0)
        trace.open("stuck", 0)
        assert trace.critical_path() == ["pass"]


class TestRendering:
    def test_the_tree_reads_with_durations_and_notes(self):
        page = pass_trace().render()
        lines = page.splitlines()
        assert lines[0] == "pass (18)"
        assert lines[1] == "  task web-0 (15)"
        assert lines[2] == "    filters (12)"
        assert lines[3] == "      - 3 nodes rejected by fits"

    def test_the_never_closed_are_named(self):
        trace = Trace()
        trace.open("pass", 0)
        trace.open("stuck", 1)
        page = trace.render()
        assert "stuck [open]" in page
        assert "WARNING: stuck never closed" in page
        assert "WARNING: pass never closed" in page
