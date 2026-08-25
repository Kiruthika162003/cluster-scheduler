from __future__ import annotations

import pytest

from fleet.errors import Invalid
from fleet.manifesttext import parse_text

GOOD = """
deploys:
  - name = web
    replicas = 4
    labels = app:web

quotas:
  - namespace = shop
    max_tasks = 20
"""


class TestHappyPath:
    def test_the_reference_file_parses(self):
        manifest = parse_text(GOOD)
        assert manifest.deploys[0].name == "web"
        assert manifest.deploys[0].replicas == 4
        assert manifest.quotas[0].namespace == "shop"

    def test_comments_and_blanks_vanish(self):
        manifest = parse_text("# nothing\n\ndeploys:\n  - name = web\n    replicas = 1\n")
        assert manifest.deploys[0].replicas == 1

    def test_labels_split_into_pairs(self):
        manifest = parse_text(
            "deploys:\n  - name = web\n    replicas = 1\n"
            "    labels = app:web, tier:front\n"
        )
        assert manifest.deploys[0].template.label_map() == {
            "app": "web", "tier": "front",
        }


class TestErrors:
    def test_an_unknown_section_names_its_line(self):
        with pytest.raises(Invalid) as caught:
            parse_text("deply:\n  - name = web\n")
        assert "line 1" in str(caught.value)

    def test_a_field_outside_an_entry_names_its_line(self):
        with pytest.raises(Invalid) as caught:
            parse_text("deploys:\n    name = web\n")
        assert "line 2" in str(caught.value)

    def test_a_wordy_number_names_field_and_line(self):
        with pytest.raises(Invalid) as caught:
            parse_text("deploys:\n  - name = web\n    replicas = many\n")
        assert "line 3" in str(caught.value)
        assert "replicas wants a number" in str(caught.value)

    def test_bad_label_syntax_is_named(self):
        with pytest.raises(Invalid) as caught:
            parse_text(
                "deploys:\n  - name = web\n    replicas = 1\n    labels = appweb\n"
            )
        assert "labels want k:v pairs" in str(caught.value)

    def test_an_entry_before_any_section_is_refused(self):
        with pytest.raises(Invalid):
            parse_text("  - name = web\n")

    def test_downstream_validation_still_applies(self):
        with pytest.raises(Invalid) as caught:
            parse_text("deploys:\n  - name = web\n")
        assert "name and replicas are required" in str(caught.value)
