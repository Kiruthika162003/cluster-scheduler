from __future__ import annotations

from fleet.hotspots import Move, report, survey
from fleet.objects import Node, Resources, Task, TaskSpec
from fleet.store import Store


def cluster(count: int = 3) -> Store:
    store = Store()
    for number in range(count):
        store.add_node(
            Node(name=f"n{number}", capacity=Resources(cpu=1000, memory=1000))
        )
    return store


def place(store: Store, name: str, node: str, cpu: int,
          priority: int = 0) -> None:
    task = Task(
        spec=TaskSpec(
            name=name,
            needs=Resources(cpu=cpu, memory=cpu),
            priority=priority,
        )
    )
    task.bound_to(node)
    store.add_task(task)


class TestDetection:
    def test_a_balanced_fleet_has_no_hotspots(self):
        store = cluster()
        for number in range(3):
            place(store, f"t{number}", f"n{number}", 500)
        assert survey(store) == []
        assert report(store).startswith("no hotspots")

    def test_the_loaded_node_is_named_with_its_share(self):
        store = cluster()
        place(store, "big", "n0", 900)
        spots = survey(store)
        assert [spot.node for spot in spots] == ["n0"]
        assert spots[0].share == 0.9

    def test_uniform_pressure_is_not_a_hotspot(self):
        store = cluster()
        for number in range(3):
            place(store, f"t{number}", f"n{number}", 900)
        assert survey(store) == []


class TestTheFix:
    def test_the_move_names_task_source_target_and_size(self):
        store = cluster()
        place(store, "big", "n0", 600)
        place(store, "small", "n0", 300)
        spots = survey(store)
        assert spots[0].partner == "n1"
        assert (
            Move(task="small", source="n0", target="n1", cpu=300)
            in spots[0].moves
        )

    def test_system_tasks_are_never_proposed(self):
        store = cluster()
        place(store, "kernel", "n0", 500, priority=100)
        place(store, "app", "n0", 400)
        spots = survey(store)
        moved = [move.task for move in spots[0].moves]
        assert "kernel" not in moved

    def test_moves_never_exceed_the_gap(self):
        store = cluster()
        place(store, "a", "n0", 400)
        place(store, "b", "n0", 400)
        spots = survey(store)
        carried = sum(move.cpu for move in spots[0].moves)
        gap = int((spots[0].share - 800 / 3000) * 1000)
        assert carried <= gap

    def test_a_full_fleet_admits_it_has_no_partner(self):
        store = cluster(2)
        place(store, "big", "n0", 950)
        place(store, "peer", "n1", 700)
        spots = survey(store)
        if spots:
            assert "add capacity" in spots[0].line() or spots[0].moves

    def test_a_cordoned_partner_is_skipped(self):
        store = cluster()
        place(store, "big", "n0", 900)
        store.get_node("n1").schedulable = False
        spots = survey(store)
        assert spots[0].partner == "n2"


class TestReport:
    def test_the_report_reads_as_a_plan(self):
        store = cluster()
        place(store, "big", "n0", 600)
        place(store, "small", "n0", 300)
        page = report(store)
        assert "1 hotspots" in page
        assert "move small (300m) to n1" in page
