from __future__ import annotations

from fleet.inhibitions import Inhibitor, Rule


def standard() -> Inhibitor:
    return Inhibitor(
        rules=[
            Rule(source_kind="node-down", consequence_kind="task-down"),
            Rule(source_kind="zone-down", consequence_kind="node-down"),
        ]
    )


class TestInhibition:
    def test_a_consequence_under_a_standing_source_is_held(self):
        inhibitor = standard()
        inhibitor.raise_source("node-down", "n2", scope="n2")
        told = inhibitor.offer("task-down", "web-4", within="n2")
        assert told is None
        assert inhibitor.source_summary("node-down", "n2") == (
            "node-down n2, 1 consequences held"
        )

    def test_a_consequence_elsewhere_still_pages(self):
        inhibitor = standard()
        inhibitor.raise_source("node-down", "n2", scope="n2")
        told = inhibitor.offer("task-down", "web-9", within="n5")
        assert told == "task-down web-9"

    def test_without_a_source_everything_pages(self):
        inhibitor = standard()
        assert inhibitor.offer("task-down", "web-4", within="n2") is not None

    def test_the_chain_inhibits_transitively_by_scope(self):
        inhibitor = standard()
        inhibitor.raise_source("zone-down", "zone-a", scope="zone-a")
        held = inhibitor.offer("node-down", "n2", within="zone-a")
        assert held is None

    def test_clearing_the_source_returns_the_count(self):
        inhibitor = standard()
        inhibitor.raise_source("node-down", "n2", scope="n2")
        for number in range(3):
            inhibitor.offer("task-down", f"web-{number}", within="n2")
        assert inhibitor.clear_source("node-down", "n2") == 3
        assert inhibitor.offer("task-down", "web-9", within="n2") is not None

    def test_the_source_page_is_the_blast_radius(self):
        inhibitor = standard()
        inhibitor.raise_source("node-down", "n2", scope="n2")
        for number in range(15):
            inhibitor.offer("task-down", f"web-{number}", within="n2")
        assert "15 consequences held" in inhibitor.source_summary(
            "node-down", "n2"
        )
