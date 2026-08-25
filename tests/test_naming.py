from __future__ import annotations

import pytest

from fleet.errors import Invalid
from fleet.naming import LIMIT, check, is_legal, sanitise


class TestChecking:
    def test_ordinary_names_pass(self):
        for name in ("web", "web-0", "a1b2", "batch-nightly-3"):
            check(name)

    def test_each_refusal_names_the_rule_and_place(self):
        cases = {
            "": "cannot be empty",
            "3web": "must start with a letter",
            "web--0": "position 5: double hyphen",
            "web_0": "'_' is not allowed",
            "web-": "cannot end with a hyphen",
        }
        for name, fragment in cases.items():
            with pytest.raises(Invalid) as caught:
                check(name)
            assert fragment in str(caught.value)

    def test_the_limit_is_exactly_sixty_three(self):
        check("a" * LIMIT)
        with pytest.raises(Invalid):
            check("a" * (LIMIT + 1))

    def test_is_legal_mirrors_check(self):
        assert is_legal("web-0")
        assert not is_legal("Web")


class TestSanitising:
    def test_arbitrary_text_becomes_a_legal_name(self):
        assert sanitise("Search Team's ETL (v2)") == "search-team-s-etl-v2"

    def test_the_result_always_passes_check(self):
        for text in ("Hello World", "--x--", "9lives", "UPPER_case"):
            check(sanitise(text))

    def test_sanitising_is_deterministic(self):
        assert sanitise("A  B") == sanitise("A  B")

    def test_nothing_legal_is_an_error(self):
        with pytest.raises(Invalid):
            sanitise("!!! ???")

    def test_leading_digits_are_trimmed_to_a_letter_start(self):
        assert sanitise("123abc").startswith("a")
