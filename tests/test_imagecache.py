from __future__ import annotations

from fleet.imagecache import PULL_TICKS, ImageCaches, image_of, start_all
from fleet.objects import Node, Resources, Task, TaskSpec
from fleet.store import Store


def imaged(name: str, image: str = "app:v1") -> Task:
    return Task(
        spec=TaskSpec(
            name=name,
            needs=Resources(cpu=100, memory=100),
            labels=(("image", image),),
        )
    )


class TestCaches:
    def test_a_warm_image_is_free(self):
        caches = ImageCaches()
        caches.warm("n0", "app:v1")
        assert caches.start_delay("n0", "app:v1") == 0
        assert caches.pulls == 0

    def test_a_cold_image_pays_the_pull_and_warms(self):
        caches = ImageCaches()
        assert caches.start_delay("n0", "app:v1") == PULL_TICKS
        assert caches.start_delay("n0", "app:v1") == 0
        assert caches.pulls == 1

    def test_caches_are_per_node(self):
        caches = ImageCaches()
        caches.warm("n0", "app:v1")
        assert not caches.has("n1", "app:v1")

    def test_the_scorer_prefers_warm_nodes(self):
        caches = ImageCaches()
        caches.warm("n0", "app:v1")
        score = caches.locality_scorer(weight=3.0)
        warm = Node(name="n0", capacity=Resources(cpu=1, memory=1))
        cold = Node(name="n1", capacity=Resources(cpu=1, memory=1))
        assert score(imaged("t"), warm, []) == 3.0
        assert score(imaged("t"), cold, []) == 0.0

    def test_imageless_tasks_score_nothing(self):
        caches = ImageCaches()
        caches.warm("n0", "app:v1")
        bare = Task(spec=TaskSpec(name="t", needs=Resources(cpu=1, memory=1)))
        node = Node(name="n0", capacity=Resources(cpu=1, memory=1))
        assert caches.locality_scorer()(bare, node, []) == 0.0
        assert image_of(bare) is None


class TestStartAll:
    def test_delays_are_charged_per_task(self):
        store = Store()
        store.add_node(Node(name="n0", capacity=Resources(cpu=1000, memory=1000)))
        first = imaged("a")
        first.bound_to("n0")
        store.add_task(first)
        second = imaged("b")
        second.bound_to("n0")
        store.add_task(second)
        caches = ImageCaches()
        delays = start_all(store, caches)
        assert delays == {"a": PULL_TICKS, "b": 0}
