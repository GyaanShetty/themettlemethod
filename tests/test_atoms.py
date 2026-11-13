import datetime as dt

import pytest
from pydantic import ValidationError

from engine import atoms

GOOD = dict(id="keep-few", type="law", pillar="relationships", number=9, title="Keep few people",
            kicker="The oath", headline="Keep few people.\nKeep them well.", sub="You become the five you sit closest to.",
            body="A short body.", source="Seneca · Letters, XIII", image="art/bond",
            publish_on=dt.date(2026, 12, 1), status="draft", channels=["instagram_plate"])


def make(**kw):
    return atoms.Atom(**{**GOOD, **kw})


def test_every_atom_in_the_repo_is_valid():
    assert len(atoms.all_atoms()) >= 5


def test_good_atom_passes():
    assert make().headline.count("\n") == 1


@pytest.mark.parametrize("change", [
    {"headline": "One.\nTwo.\nThree.\nFour."},                 # more than three lines
    {"headline": "Keep few people"},                           # no full stop
    {"headline": "Five Friendship Hacks You Need Now."},       # title case
    {"headline": "Keep few people!"},                          # exclamation mark
    {"headline": "This line is far too long to sit on a plate at any size we allow."},
    {"source": None},                                          # a law with no source
    {"source": "Seneca"},                                      # source without its work
    {"image": "art/not-there"},
    {"pillar": "money"},
    {"channels": []},
])
def test_bad_atoms_are_rejected(change):
    with pytest.raises(ValidationError):
        make(**change)


def test_a_draft_is_never_publishable():
    assert not make(status="draft").publishable
    assert not make(status="held").publishable
    assert make(status="approved").publishable
