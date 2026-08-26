from __future__ import annotations

import pytest

from fleet.errors import Invalid
from fleet.phidetect import PhiDetector


def steady_peer(detector: PhiDetector, name: str, beats: int = 10) -> None:
    for count in range(beats):
        detector.heartbeat(name, now=count * 10)


def jittery_peer(detector: PhiDetector, name: str) -> None:
    now = 0
    for count in range(10):
        now += 5 if count % 2 else 15
        detector.heartbeat(name, now=now)


class TestTheModel:
    def test_a_present_peer_is_unsuspicious(self):
        detector = PhiDetector()
        steady_peer(detector, "n0")
        assert detector.suspicion("n0", now=91) == 0.0

    def test_suspicion_climbs_with_silence(self):
        detector = PhiDetector()
        steady_peer(detector, "n0")
        early = detector.suspicion("n0", now=105)
        late = detector.suspicion("n0", now=150)
        assert 0.0 < early < late

    def test_too_few_samples_stay_silent(self):
        detector = PhiDetector()
        detector.heartbeat("new", now=0)
        detector.heartbeat("new", now=10)
        assert detector.suspicion("new", now=100) == 0.0

    def test_the_never_seen_are_refused(self):
        with pytest.raises(Invalid):
            PhiDetector().suspicion("ghost", now=0)

    def test_backwards_heartbeats_are_refused(self):
        detector = PhiDetector()
        detector.heartbeat("n0", now=10)
        with pytest.raises(Invalid):
            detector.heartbeat("n0", now=5)


class TestRhythms:
    def test_the_steady_peer_is_condemned_faster(self):
        detector = PhiDetector()
        steady_peer(detector, "steady")
        jittery_peer(detector, "jittery")
        silence = 25
        steady_phi = detector.suspicion("steady", now=90 + silence)
        jittery_phi = detector.suspicion("jittery", now=100 + silence)
        assert steady_phi > jittery_phi

    def test_a_recovered_peer_resets_its_story(self):
        detector = PhiDetector()
        steady_peer(detector, "n0")
        assert detector.suspicion("n0", now=140) > 1.0
        detector.heartbeat("n0", now=140)
        assert detector.suspicion("n0", now=145) == 0.0


class TestThresholds:
    def test_one_detector_many_verdicts(self):
        detector = PhiDetector()
        steady_peer(detector, "n0")
        now = 102
        cautious = detector.suspects(now, threshold=1.0)
        drastic = detector.suspects(now, threshold=8.0)
        assert cautious == ["n0"]
        assert drastic == []

    def test_the_report_reads_per_peer(self):
        detector = PhiDetector()
        steady_peer(detector, "n0")
        page = detector.report(now=91)
        assert page == "n0: phi 0.0"
        assert PhiDetector().report(now=0) == "no peers"
