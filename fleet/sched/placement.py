"""The placement engine: queue, filters, preemption and the class treaty,
one front door.

The pieces exist separately so they can be measured separately; the
engine is where they meet. A submitted task enters the queue; each pass
takes the ready tasks in priority order, tries the filters, and on
refusal either benches the task or, when the class treaty allows it,
buys room by preemption and places into it. Every displaced task
re-enters the queue rather than vanishing, and every decision lands in
the journal with its reason.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from fleet.audit import Journal
from fleet.control.budget import Guard
from fleet.errors import Unschedulable
from fleet.objects import Task
from fleet.sched.classes import Verdicts, class_of
from fleet.sched.core import Scheduler
from fleet.sched.preempt import Preemptor
from fleet.sched.queue import SchedulingQueue
from fleet.store import Store


@dataclass
class Engine:
    scheduler: Scheduler = field(default_factory=Scheduler)
    preemptor: Preemptor = field(default_factory=Preemptor)
    queue: SchedulingQueue = field(default_factory=SchedulingQueue)
    verdicts: Verdicts = field(default_factory=Verdicts)
    guard: Guard | None = None
    max_displacements_per_pass: int = 10**9
    journal: Journal = field(default_factory=Journal)
    placed: int = 0
    displaced: int = 0
    preemptions_vetoed: int = 0
    churn_deferred: int = 0

    def submit(self, store: Store, task: Task) -> None:
        store.add_task(task)
        self.queue.offer(task.spec.name, task.spec.priority, task.spec.namespace)

    def _may_preempt_for(self, store: Store, task: Task) -> bool:
        mover = class_of(task.spec.priority)
        plan_possible = False
        for node in store.nodes.values():
            plan = self.preemptor.plan_for_node(task, node, store.active_tasks())
            if plan is None or not plan.victims:
                if plan is not None and not plan.victims:
                    return False
                continue
            victims_allowed = all(
                self.verdicts.may_displace(
                    mover, class_of(store.get_task(name).spec.priority)
                )
                for name in plan.victims
            )
            if victims_allowed:
                plan_possible = True
        return plan_possible

    def _budget_permits(self, store: Store, task: Task) -> bool:
        if self.guard is None:
            return True
        for node in store.nodes.values():
            plan = self.preemptor.plan_for_node(task, node, store.active_tasks())
            if plan is None:
                continue
            if all(
                self.guard.may_evict(store, victim)[0] for victim in plan.victims
            ):
                return True
        self.preemptions_vetoed += 1
        return False

    def one_pass(self, store: Store, now: int) -> tuple[int, int]:
        placed = benched = 0
        displaced_this_pass = 0
        for name in self.queue.ready(now):
            task = store.get_task(name)
            try:
                chosen = self.scheduler.schedule(store, task)
                self.journal.note(
                    now, "engine", name, "bind", f"{chosen.name} accepted"
                )
                self.queue.forget(name)
                self.placed += 1
                placed += 1
                continue
            except Unschedulable:
                pass
            churn_left = self.max_displacements_per_pass - displaced_this_pass
            if churn_left <= 0:
                self.churn_deferred += 1
                wait = self.queue.refuse(name, now)
                self.journal.note(
                    now, "engine", name, "bench",
                    f"churn budget spent, back in {wait}",
                )
                benched += 1
                continue
            if self._may_preempt_for(store, task) and self._budget_permits(
                store, task
            ):
                plan = self.preemptor.make_room(store, task)
                for victim_name in plan.victims:
                    victim = store.get_task(victim_name)
                    generation = victim.generation
                    victim.phase = "Pending"
                    store.update_task(victim, read_generation=generation)
                    self.queue.offer(victim_name, victim.spec.priority, victim.spec.namespace)
                    self.displaced += 1
                    displaced_this_pass += 1
                    self.journal.note(
                        now, "engine", victim_name, "displace",
                        f"room for {name}",
                    )
                chosen = self.scheduler.schedule(store, task)
                self.journal.note(
                    now, "engine", name, "bind", f"{chosen.name} after preemption"
                )
                self.queue.forget(name)
                self.placed += 1
                placed += 1
            else:
                wait = self.queue.refuse(name, now)
                self.journal.note(
                    now, "engine", name, "bench", f"no fit, back in {wait}"
                )
                benched += 1
        return placed, benched
