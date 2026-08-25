from __future__ import annotations

from fleet.admissionlog import AdmissionLog


def storied_log() -> AdmissionLog:
    log = AdmissionLog()
    log.refuse(2, "web-0", "quota", "search is at its cpu ceiling")
    log.refuse(15, "web-0", "hooks", "missing team label")
    log.refuse(20, "web-0", "fits", "no node has 4000m")
    log.admit(25, "web-0")
    log.refuse(5, "batch-1", "quota", "batch is at its task ceiling")
    return log


class TestTimeline:
    def test_one_task_reads_as_one_story(self):
        page = storied_log().timeline("web-0")
        assert page.splitlines() == [
            "web-0:",
            "  [2] refused by quota: search is at its cpu ceiling",
            "  [15] refused by hooks: missing team label",
            "  [20] refused by fits: no node has 4000m",
            "  [25] admitted",
        ]

    def test_the_unadmitted_end_still_outside(self):
        page = storied_log().timeline("batch-1")
        assert page.endswith("still outside")

    def test_the_never_seen_are_named(self):
        assert storied_log().timeline("ghost") == "ghost: never seen"

    def test_admission_without_refusals_is_a_clean_story(self):
        log = AdmissionLog()
        log.admit(1, "easy")
        assert log.timeline("easy").splitlines() == ["easy:", "  [1] admitted"]


class TestReportCard:
    def test_reversals_count_only_later_admissions(self):
        book = storied_log().by_gate()
        assert book["quota"] == {"refusals": 2, "reversed": 1}
        assert book["fits"] == {"refusals": 1, "reversed": 1}

    def test_the_card_judges_each_gate(self):
        log = AdmissionLog()
        for number in range(4):
            log.refuse(number, f"t{number}", "hooks", "missing label")
            log.admit(number + 10, f"t{number}")
        log.refuse(0, "solid", "quota", "over ceiling")
        card = log.report_card()
        assert "hooks: 4 refusals, 4 reversed (mostly reversed" in card
        assert "quota: 1 refusals, 0 reversed (mostly final" in card

    def test_an_empty_log_says_so(self):
        assert AdmissionLog().report_card() == "no refusals recorded"
