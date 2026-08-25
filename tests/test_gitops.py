from __future__ import annotations

import pytest

from fleet.errors import Invalid
from fleet.gitops import Repo, Syncer
from fleet.manifest import parse
from fleet.store import Store


def manifest(replicas: int):
    return parse({"deploys": [{"name": "web", "replicas": replicas}]})


class TestRepo:
    def test_commits_number_from_one(self):
        repo = Repo()
        first = repo.commit(manifest(2), "birth")
        assert first.revision == 1
        assert repo.head().message == "birth"

    def test_an_empty_repo_has_no_head(self):
        with pytest.raises(Invalid):
            Repo().head()


class TestSync:
    def test_the_first_sync_advances_and_builds(self):
        store = Store()
        repo = Repo()
        repo.commit(manifest(3), "launch web")
        syncer = Syncer()
        line = syncer.sync(store, repo)
        assert line == "advanced to r1: launch web"
        assert len(store.tasks) == 3

    def test_a_steady_cluster_syncs_quietly(self):
        store = Store()
        repo = Repo()
        repo.commit(manifest(3), "launch")
        syncer = Syncer()
        syncer.sync(store, repo)
        assert syncer.sync(store, repo) == "r1 steady"

    def test_a_new_commit_moves_the_cluster(self):
        store = Store()
        repo = Repo()
        repo.commit(manifest(3), "launch")
        syncer = Syncer()
        syncer.sync(store, repo)
        repo.commit(manifest(5), "scale for launch day")
        line = syncer.sync(store, repo)
        assert line == "advanced to r2: scale for launch day"
        assert len(store.tasks) == 5

    def test_the_hand_edit_survives_only_until_the_sync(self):
        store = Store()
        repo = Repo()
        repo.commit(manifest(3), "launch")
        syncer = Syncer()
        syncer.sync(store, repo)
        store.remove_task("web-2")
        line = syncer.sync(store, repo)
        assert line == "r1 re-imposed, corrected 1 drifted"
        assert len(store.tasks) == 3
        assert syncer.corrections == 1

    def test_committing_the_edit_makes_it_policy(self):
        store = Store()
        repo = Repo()
        repo.commit(manifest(3), "launch")
        syncer = Syncer()
        syncer.sync(store, repo)
        store.remove_task("web-2")
        repo.commit(manifest(2), "shrink: the 2am fix was right")
        syncer.sync(store, repo)
        assert len(store.tasks) == 2
        assert syncer.corrections == 0
