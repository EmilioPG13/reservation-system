"""The checks of `create-admin` that run before it touches the database."""

import pytest

from app import cli


def feed_passwords(monkeypatch: pytest.MonkeyPatch, *answers: str) -> None:
    replies = iter(answers)
    monkeypatch.setattr(cli.getpass, "getpass", lambda _prompt: next(replies))


def test_a_short_password_is_refused(monkeypatch: pytest.MonkeyPatch, capsys):
    feed_passwords(monkeypatch, "short")

    code = cli.main(["create-admin", "--email", "a@example.com", "--name", "A"])

    assert code == 1
    assert "at least" in capsys.readouterr().err


def test_mismatched_passwords_are_refused(monkeypatch: pytest.MonkeyPatch, capsys):
    feed_passwords(monkeypatch, "correct horse battery", "correct horse batterY")

    code = cli.main(["create-admin", "--email", "a@example.com", "--name", "A"])

    assert code == 1
    assert "do not match" in capsys.readouterr().err
