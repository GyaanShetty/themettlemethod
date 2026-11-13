import pytest

from engine import social


@pytest.fixture(scope="session")
def browser():
    with social.browser() as b:
        yield b
