from __future__ import annotations

from fleet.control.budget import Budget, Guard
from fleet.objects import Node, Resources, Task, TaskSpec
from fleet.preflight import drain_preflight, upgrade_preflight
from fleet.skewpolicy import SkewGate
from fleet.store import Store


def webbed(cpu_each: int = 300) -> tuple[Store, Guard]:
    store = Store()
    for number in range(3):
        store.add_node(
            Node(name=f"n{number}", capacity=Resources(cpu=1000, memory=1000))
        )
    for number, home in enumerate(["n0", "n1", "n2"]):
        task = Task(
            spec=TaskSpec(
                name=f"w{number}",
                needs=Resources(cpu=cpu_each, memory=cpu_each),
                labels=(("app", "web"),),
            )
        )
        task.bound_to(home)
        store.add_task(task)
    guard = Guard(
        budgets=[
            Budget(
                name="floor",
                selector_key="app",
                selector_value="web",
                min_available=2,
            )
        ]
    )
    return store, guard


class TestDrainPreflight:
    def test_a_roomy_drain_is_go(self):
        store, guard = webbed()
        assert drain_preflight(store, guard, "n0").go()

    def test_a_ghost_node_is_the_only_objection(self):
        store, guard = webbed()
        verdict = drain_preflight(store, guard, "ghost")
        assert verdict.objections == ["ghost does not exist"]

    def test_a_capacity_shortfall_is_measured(self):
        store, guard = webbed(cpu_each=450)
        held = store.get_task("w2")
        generation = held.generation
        held.node = "n0"
        store.update_task(held, read_generation=generation)
        store.get_node("n2").schedulable = False
        verdict = drain_preflight(store, guard, "n0")
        assert not verdict.go()
        assert any(
            "the rest of the fleet has 550m free" in objection
            for objection in verdict.objections
        )

    def test_a_budget_refusal_is_listed_by_name(self):
        store, guard = webbed()
        for name in ("w1", "w2"):
            held = store.get_task(name)
            generation = held.generation
            held.phase = "Succeeded"
            held.node = None
            store.update_task(held, read_generation=generation)
        verdict = drain_preflight(store, guard, "n0")
        assert any("w0" in objection for objection in verdict.objections)

    def test_an_inconsistent_cluster_objects_first(self):
        store, guard = webbed()
        stray = Task(spec=TaskSpec(name="stray", needs=Resources(cpu=1, memory=1)))
        stray.phase = "Bound"
        store.add_task(stray)
        verdict = drain_preflight(store, guard, "n0")
        assert "already inconsistent" in verdict.objections[0]


class TestUpgradePreflight:
    def gated(self) -> tuple[Store, SkewGate]:
        store, _ = webbed()
        gate = SkewGate(control_plane="1.28")
        gate.admit_node("n0", "1.27")
        gate.admit_node("n1", "1.28")
        return store, gate

    def test_a_safe_upgrade_is_go(self):
        store, gate = self.gated()
        assert upgrade_preflight(store, gate, "1.29").go()

    def test_every_objection_arrives_at_once(self):
        store, gate = self.gated()
        gate.node_versions["n0"] = "1.26"
        for number, home in enumerate(["n0", "n1"]):
            heavy = Task(
                spec=TaskSpec(
                    name=f"fat{number}", needs=Resources(cpu=650, memory=650)
                )
            )
            heavy.bound_to(home)
            store.add_task(heavy)
        verdict = upgrade_preflight(store, gate, "1.29")
        assert len(verdict.objections) == 2
        assert any("N+1" in objection for objection in verdict.objections)
        assert any("orphan" in objection for objection in verdict.objections)

    def test_the_probe_never_moves_the_real_gate(self):
        store, gate = self.gated()
        gate.node_versions["n0"] = "1.26"
        upgrade_preflight(store, gate, "1.29")
        assert gate.control_plane == "1.28"

    def test_the_verdict_line_reads_go_or_no_go(self):
        store, gate = self.gated()
        assert upgrade_preflight(store, gate, "1.29").line().endswith(": go")
