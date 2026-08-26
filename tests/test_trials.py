from __future__ import annotations

import importlib

import pytest

from fleet.trials import (
    backfillrent,
    balloonpay,
    bigfleet,
    burnalarm,
    canaryevidence,
    cascade,
    chaosfloor,
    chattyhops,
    churnbudget,
    coldpull,
    datagravity,
    dealrestart,
    drainfloor,
    duckbill,
    eightbox,
    fairqueue,
    fencerace,
    filterorder,
    fragmentation,
    ganghostages,
    ghosts,
    grandtour,
    greenshift,
    hedgeprice,
    hotmoves,
    kernelwalk,
    longhaul,
    moneybill,
    nightshift,
    noisyfair,
    oldiron,
    oscillation,
    overcommit,
    packing,
    promisekeeper,
    queueknee,
    reboot,
    robotstop,
    rollbacklag,
    rolloutpace,
    scalerfight,
    scrubpromise,
    shadowdiff,
    sketchbill,
    slivers,
    slowstart,
    softstep,
    spikewave,
    splitbrain,
    splitcalm,
    spotnotice,
    staleaddress,
    starvation,
    strandedmemory,
    twobills,
    twochoices,
    warmupdebt,
    wrongprobe,
    zoneloss,
)
from fleet.trials.registry import TRIALS, all_verdicts, broken, report
from fleet.trials.verdict import Verdict


class TestVerdict:
    def test_the_line_carries_the_mark_and_numbers(self):
        verdict = Verdict(trial="t", sentence="s", numbers={"a": 1}, holds=True)
        assert verdict.line() == "t: s [holds] (a=1)"

    def test_a_broken_verdict_says_so(self):
        verdict = Verdict(trial="t", sentence="s", holds=False)
        assert "BROKEN" in verdict.line()


class TestEveryTrial:
    @pytest.mark.parametrize(
        "trial",
        [
            fragmentation,
            ghosts,
            cascade,
            oscillation,
            drainfloor,
    fairqueue,
            rolloutpace,
            canaryevidence,
            overcommit,
            ganghostages,
            slivers,
            warmupdebt,
    zoneloss,
            packing,
    reboot,
            chaosfloor,
            moneybill,
            starvation,
            kernelwalk,
    longhaul,
            spotnotice,
            softstep,
            noisyfair,
            splitbrain,
            rollbacklag,
            filterorder,
            balloonpay,
            twobills,
            wrongprobe,
            scalerfight,
            datagravity,
            chattyhops,
    coldpull,
            spikewave,
            oldiron,
            staleaddress,
            coldpull,
            twochoices,
            longhaul,
            fairqueue,
            reboot,
            zoneloss,
            churnbudget,
            shadowdiff,
            robotstop,
            nightshift,
            promisekeeper,
            bigfleet,
            strandedmemory,
            grandtour,
            slowstart,
            dealrestart,
            burnalarm,
            fencerace,
            greenshift,
            hotmoves,
            backfillrent,
            hedgeprice,
            splitcalm,
            queueknee,
            eightbox,
            sketchbill,
            scrubpromise,
            duckbill,
        ],
    )
    def test_the_trial_holds(self, trial):
        verdict = trial.run()
        assert verdict.holds, verdict.line()

    def test_the_registry_lists_them_all(self):
        assert len(all_verdicts()) == len(TRIALS)

    def test_nothing_is_broken(self):
        assert broken() == []

    def test_the_report_renders_every_line(self):
        text = report()
        assert "fragmentation" in text and "0 broken" in text

    def test_every_trial_name_matches_its_module(self):
        for dotted in TRIALS:
            module = importlib.import_module(dotted)
            verdict = module.run()
            assert verdict.trial == dotted.rsplit(".", 1)[1]

    def test_no_trial_is_registered_twice(self):
        assert len(TRIALS) == len(set(TRIALS))

    def test_every_verdict_carries_numbers(self):
        for dotted in TRIALS:
            module = importlib.import_module(dotted)
            assert module.run().numbers
