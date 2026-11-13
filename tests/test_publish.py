import datetime as dt

import pytest

from engine import atoms, ledger, publish, state


class Fake(publish.Publisher):
    sent = 0
    fail = False

    def send(self, a):
        if self.fail:
            raise RuntimeError("platform down")
        Fake.sent += 1
        return publish.Result("ext-1", "https://example.org/p/1")


@pytest.fixture
def world(tmp_path, monkeypatch):
    monkeypatch.setattr(state, "PATH", tmp_path / "state.json")
    for k in ("SUPABASE_URL", "SUPABASE_SERVICE_ROLE_KEY", "IG_ACCESS_TOKEN"):
        monkeypatch.delenv(k, raising=False)
    fake = Fake("threads", ())
    Fake.sent, fake.fail = 0, False
    monkeypatch.setitem(publish.PUBLISHERS, "threads", fake)
    a = atoms.get("inversion").model_copy(update={"channels": ["threads"]})
    return a, fake


def test_default_is_a_dry_run(world):
    a, _ = world
    assert ledger.publish_live() is False
    assert publish.run(a) == {"threads": "dry run"} and Fake.sent == 0
    assert state.load()["posts"] == {}


def test_live_posts_once_and_only_once(world):
    a, _ = world
    assert publish.run(a, live=True) == {"threads": "posted"}
    assert publish.run(a, live=True) == {"threads": "already posted"}
    assert Fake.sent == 1
    assert state.load()["posts"]["inversion"]["threads"]["external_id"] == "ext-1"


def test_an_unapproved_atom_never_posts(world):
    a, _ = world
    assert publish.run(a.model_copy(update={"status": "draft"}), live=True) == {"threads": "dry run"} and Fake.sent == 0


def test_missing_secrets_mean_not_connected_and_a_dry_run(world):
    a, _ = world
    b = a.model_copy(update={"channels": ["instagram_story"]})
    (publish.BUILD / "social" / b.id).mkdir(parents=True, exist_ok=True)
    (publish.BUILD / "social" / b.id / "story.png").touch()
    assert "IG_ACCESS_TOKEN" in publish.connections()["instagram_story"]
    assert publish.run(b, live=True) == {"instagram_story": "dry run"}


def test_a_failure_is_recorded_and_can_be_retried(world):
    a, fake = world
    fake.fail = True
    assert publish.run(a, live=True) == {"threads": "failed"}
    fake.fail = False
    assert publish.run(a, live=True) == {"threads": "posted"} and Fake.sent == 1


def test_going_live_does_not_release_a_backlog(world):
    a, _ = world
    day = dt.date(2026, 12, 10)
    old, today = a.model_copy(update={"publish_on": dt.date(2026, 11, 3)}), a.model_copy(update={"id": "today", "publish_on": day})
    assert [x.id for x in publish.due(day, [old, today])] == ["today"]


def test_caption_has_five_hashtags_and_no_hype(world):
    a, _ = world
    c = publish.caption(a)
    assert c.count("#") == 5 and "!" not in c and "#mettlemethod" in c
