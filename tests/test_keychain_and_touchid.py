from types import SimpleNamespace

import pytest

import cypher.main as cypher


def test_save_private_key_password_to_keychain_calls_security(monkeypatch) -> None:
    calls = []

    def fake_run(command, check, **kwargs):
        calls.append((command, check, kwargs))
        return SimpleNamespace(returncode=0, stdout="")

    monkeypatch.setattr(cypher.subprocess, "run", fake_run)

    cypher.save_private_key_password_to_keychain("secret")

    command, check, _kwargs = calls[0]

    assert check is True
    assert command[:2] == ["security", "add-generic-password"]
    assert "secret" in command


def test_load_private_key_password_from_keychain_returns_password(monkeypatch) -> None:
    def fake_run(command, check, capture_output, text):
        return SimpleNamespace(returncode=0, stdout="password\n")

    monkeypatch.setattr(cypher.subprocess, "run", fake_run)

    assert cypher.load_private_key_password_from_keychain() == "password"


def test_load_private_key_password_from_keychain_returns_none_on_failure(
    monkeypatch,
) -> None:
    def fake_run(command, check, capture_output, text):
        return SimpleNamespace(returncode=1, stdout="")

    monkeypatch.setattr(cypher.subprocess, "run", fake_run)

    assert cypher.load_private_key_password_from_keychain() is None


def test_delete_private_key_password_from_keychain_calls_security(monkeypatch) -> None:
    calls = []

    def fake_run(command, check, capture_output, text):
        calls.append((command, check, capture_output, text))
        return SimpleNamespace(returncode=0, stdout="")

    monkeypatch.setattr(cypher.subprocess, "run", fake_run)

    cypher.delete_private_key_password_from_keychain()

    command, check, capture_output, text = calls[0]

    assert command[:2] == ["security", "delete-generic-password"]
    assert check is False
    assert capture_output is True
    assert text is True


class FakeTouchIDContext:
    def __init__(self, can_evaluate=True, auth_success=True):
        self.can_evaluate = can_evaluate
        self.auth_success = auth_success

    def canEvaluatePolicy_error_(self, policy, error):
        return self.can_evaluate, None

    def evaluatePolicy_localizedReason_reply_(self, policy, reason, reply):
        reply(self.auth_success, "denied")


class FakeTouchIDFactory:
    def __init__(self, context):
        self.context = context

    def alloc(self):
        return self

    def init(self):
        return self.context


def test_require_touch_id_accepts_success(monkeypatch) -> None:
    monkeypatch.setattr(
        cypher,
        "LAContext",
        FakeTouchIDFactory(
            FakeTouchIDContext(can_evaluate=True, auth_success=True)
        ),
    )

    cypher.require_touch_id("reason")


def test_require_touch_id_rejects_unavailable(monkeypatch) -> None:
    monkeypatch.setattr(
        cypher,
        "LAContext",
        FakeTouchIDFactory(
            FakeTouchIDContext(can_evaluate=False, auth_success=False)
        ),
    )

    with pytest.raises(PermissionError, match="Touch ID is not available"):
        cypher.require_touch_id("reason")


def test_require_touch_id_rejects_failed_auth(monkeypatch) -> None:
    monkeypatch.setattr(
        cypher,
        "LAContext",
        FakeTouchIDFactory(
            FakeTouchIDContext(can_evaluate=True, auth_success=False)
        ),
    )

    with pytest.raises(PermissionError, match="Touch ID authentication failed"):
        cypher.require_touch_id("reason")
