# cluster-scheduler

A declarative cluster orchestrator built as a working model of how a
fleet is actually run: a versioned store with an event log, a
placement engine fed only through its scheduling queue, controllers
that reconcile deploys and nodes and jobs, rollout machinery with
canaries and freezes, and the operational organs around them, from
alert routing and SLO burn meters to live migration, work stealing,
and the quarterly capacity review.

The package is `fleet`: 30,000 lines of strict code (docstrings,
comments, and blank lines not counted), 1,763 tests, all green.

## What is inside

**The core.** `fleet/store.py` holds nodes and tasks behind
generation-checked updates and a monotonic event log; `fleet/sched/`
holds the filters, scorers, priority bands, preemption treaty, DRF
quota, gang scheduling, deadline scheduling, and the placement
engine whose rule is that nothing reaches it except through the
queue. `fleet/control/` reconciles deploys, node health, budgets,
hooks, endpoints, cron, DAG jobs, and finalizers. `fleet/roll/`
carries rolling updates, canaries with evidence thresholds,
blue-green, waves, and auto-pause.

**The operational organs.** Alert routing with escalation ladders,
SLO burn meters with the dual-window alarm, error-budget freezes
with break-glass, node quarantine with probation, capacity
forecasting, hotspot plans that never create the hotspot they fix,
leader election with fencing tokens, circuit breakers, retry
budgets, bulkheads, hedging, single flight, adaptive concurrency,
consistent hashing, shard autosplit, watermarks, rollup ladders,
tail sampling, phi-accrual failure detection, clock skew bounds,
work stealing, live migration, graceful shutdown, sagas, device
scheduling with the eight-box rule, and the ledgers: toil, MTBF,
delivery, patch compliance, inventory, libyears.

**The measured story.** 59 trials in `fleet/trials/` are experiments
whose conclusions are pinned to measured numbers; when a guess was
wrong, the docstring keeps the guess beside the truth, because the
distance between them is the finding. 45 conformance checks across
eight waves state the promises in operator language and verify each
with the smallest scenario that would catch it breaking. 19 runnable
examples in `examples/` compose the organs into days: an incident, a
launch, a Black Friday, a NOC week, a storm drill, an ops review.

## Running it

```bash
python -m pytest tests/ -q          # 1,763 tests
python -m fleet.cli trials          # 59 trials with their numbers
python -m fleet.cli conformance     # 45 promises, each verified
python -m fleet.cli bench           # scheduling complexity, gated
python -m fleet.cli summary         # the whole story in one line
python -m examples.fullday          # one full day, four acts
```

No dependencies beyond Python 3.11+ and pytest for the test suite.

## The style of the thing

Every module states what it does and why the design is shaped that
way, in its docstring, with the measured numbers where measurement
happened. Errors are named refusals, not stack traces. Reports are
sentences an operator would say. The suite's rule for itself is the
repository's rule for everything: a claim without a number attached
is a feeling, and feelings do not page.

## Attribution

Written by Kiruthika Subramani in collaboration with Claude,
Anthropic's AI assistant.
