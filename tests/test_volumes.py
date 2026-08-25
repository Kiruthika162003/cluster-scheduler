from __future__ import annotations

import pytest

from fleet.errors import Invalid, NotFound
from fleet.objects import Node, Resources, Task, TaskSpec
from fleet.volumes import Volume, VolumeBook


def book_with_shard() -> VolumeBook:
    book = VolumeBook()
    book.add(Volume(name="shard", size=500, home="n0"))
    return book


def task(name: str = "t") -> Task:
    return Task(spec=TaskSpec(name=name, needs=Resources(cpu=100, memory=100)))


class TestBook:
    def test_a_volume_registers_once(self):
        book = book_with_shard()
        with pytest.raises(Invalid):
            book.add(Volume(name="shard", size=1, home="n1"))

    def test_a_claim_names_the_home(self):
        book = book_with_shard()
        book.claim("t", "shard")
        assert book.home_of("t") == "n0"

    def test_claiming_a_ghost_volume_fails(self):
        with pytest.raises(NotFound):
            book_with_shard().claim("t", "ghost")

    def test_a_second_claim_on_another_volume_is_refused(self):
        book = book_with_shard()
        book.add(Volume(name="other", size=1, home="n1"))
        book.claim("t", "shard")
        with pytest.raises(Invalid):
            book.claim("t", "other")

    def test_reclaiming_the_same_volume_is_fine(self):
        book = book_with_shard()
        book.claim("t", "shard")
        book.claim("t", "shard")
        assert book.home_of("t") == "n0"

    def test_an_unclaimed_task_has_no_home(self):
        assert book_with_shard().home_of("free") is None


class TestGravityFilter:
    def test_the_home_node_passes(self):
        book = book_with_shard()
        book.claim("t", "shard")
        check = book.gravity_filter()
        home = Node(name="n0", capacity=Resources(cpu=1, memory=1))
        assert check(task(), home, []) is None

    def test_every_other_node_is_refused_with_the_home_named(self):
        book = book_with_shard()
        book.claim("t", "shard")
        check = book.gravity_filter()
        away = Node(name="n1", capacity=Resources(cpu=1, memory=1))
        assert check(task(), away, []) == "volume lives on n0"

    def test_unclaimed_tasks_pass_everywhere(self):
        check = book_with_shard().gravity_filter()
        anywhere = Node(name="n7", capacity=Resources(cpu=1, memory=1))
        assert check(task("free"), anywhere, []) is None


class TestMigration:
    def test_the_cost_is_size_over_rate_rounded_up(self):
        book = book_with_shard()
        assert book.migrate("shard", "n1", copy_rate=200) == 3
        assert book.volumes["shard"].home == "n1"

    def test_a_move_to_home_is_free(self):
        book = book_with_shard()
        assert book.migrate("shard", "n0") == 0

    def test_migrations_are_recorded(self):
        book = book_with_shard()
        book.migrate("shard", "n1")
        assert book.migrations == [("shard", "n0", "n1", 5)]

    def test_migrating_a_ghost_fails(self):
        with pytest.raises(NotFound):
            book_with_shard().migrate("ghost", "n1")

