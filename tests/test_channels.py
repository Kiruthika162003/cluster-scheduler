from __future__ import annotations

import pytest

from fleet.channels import SOAK, Channels
from fleet.errors import Invalid


class TestPromotion:
    def test_a_release_lands_in_rapid_only(self):
        channels = Channels()
        channels.release("v1", now=0)
        assert channels.version_for("rapid") == "v1"
        assert channels.version_for("stable") is None

    def test_the_soak_promotes_to_stable(self):
        channels = Channels()
        channels.release("v1", now=0)
        channels.tick(now=SOAK - 1)
        assert channels.stable is None
        channels.tick(now=SOAK)
        assert channels.stable == "v1"

    def test_a_newer_rapid_restarts_the_soak(self):
        channels = Channels()
        channels.release("v1", now=0)
        channels.release("v2", now=SOAK - 5)
        channels.tick(now=SOAK)
        assert channels.stable is None
        channels.tick(now=SOAK - 5 + SOAK)
        assert channels.stable == "v2"


class TestYanks:
    def test_a_yank_clears_the_channel_and_freezes(self):
        channels = Channels()
        channels.release("v1", now=0)
        channels.yank("v1", now=5)
        assert channels.rapid is None and channels.frozen

    def test_a_frozen_channel_never_promotes(self):
        channels = Channels()
        channels.release("v1", now=0)
        channels.tick(now=SOAK)
        channels.release("v2", now=SOAK + 1)
        channels.yank("v2", now=SOAK + 2)
        channels.tick(now=SOAK * 3)
        assert channels.stable == "v1"

    def test_a_yanked_build_in_stable_is_pulled_too(self):
        channels = Channels()
        channels.release("v1", now=0)
        channels.tick(now=SOAK)
        channels.yank("v1", now=SOAK + 1)
        assert channels.stable is None

    def test_the_fix_unfreezes_and_the_bug_cannot_return(self):
        channels = Channels()
        channels.release("v1", now=0)
        channels.yank("v1", now=1)
        channels.release("v2", now=2)
        assert not channels.frozen
        with pytest.raises(Invalid):
            channels.release("v1", now=3)

    def test_unknown_channels_are_refused(self):
        with pytest.raises(Invalid):
            Channels().version_for("bleeding")
