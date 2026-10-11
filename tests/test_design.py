"""Claude Design logins switched independently of the Code login (design.py)."""

from __future__ import annotations

import json

import pytest

from claude_swap import design
from claude_swap.exceptions import (
    AccountNotFoundError,
    CredentialReadError,
    ValidationError,
)
from claude_swap.models import Platform
from claude_swap.paths import get_credentials_path
from claude_swap.settings import load_swap_settings
from claude_swap.switcher import ClaudeAccountSwitcher

CODE = {"accessToken": "code", "refreshToken": "code-rt"}


@pytest.fixture
def switcher(temp_home):
    s = ClaudeAccountSwitcher()
    s.platform = Platform.LINUX  # file-backed live store and backups
    s._setup_directories()
    return s


def set_live(design_login=None, code=CODE):
    blob = {"claudeAiOauth": code}
    if design_login is not None:
        blob["designOauth"] = design_login
    get_credentials_path().write_text(json.dumps(blob))


def live():
    return json.loads(get_credentials_path().read_text())


def stored(s, name):
    raw = s._store._read_account_credentials("design", name)
    return json.loads(raw) if raw else None


def test_add_saves_live_login_and_keeps_it_across_code_switches(switcher):
    set_live({"refreshToken": "p1"})
    design.add(switcher, "personal")

    assert stored(switcher, "personal") == {"refreshToken": "p1"}
    assert design.load_state(switcher) == (["personal"], "personal")
    assert load_swap_settings(switcher.backup_dir).design_login is False


def test_add_needs_a_live_design_login_and_a_safe_name(switcher):
    set_live()
    with pytest.raises(CredentialReadError):
        design.add(switcher, "personal")
    with pytest.raises(ValidationError):
        design.add(switcher, "../evil")


def test_use_saves_rotated_live_back_and_leaves_code_login(switcher):
    set_live({"refreshToken": "w1"})
    design.add(switcher, "work")
    set_live({"refreshToken": "p1"})
    design.add(switcher, "personal")
    set_live({"refreshToken": "p2"})  # Claude Code rotated personal's token

    assert design.use(switcher, "work") is True

    assert live() == {"claudeAiOauth": CODE, "designOauth": {"refreshToken": "w1"}}
    assert stored(switcher, "personal") == {"refreshToken": "p2"}
    assert design.load_state(switcher) == (["work", "personal"], "work")


def test_use_active_is_a_noop_and_unknown_raises(switcher):
    set_live({"refreshToken": "p1"})
    design.add(switcher, "personal")

    assert design.use(switcher, "personal") is False
    with pytest.raises(AccountNotFoundError):
        design.use(switcher, "nope")


def test_use_needs_a_live_code_login(switcher):
    set_live({"refreshToken": "p1"})
    design.add(switcher, "personal")
    set_live({"refreshToken": "w1"})
    design.add(switcher, "work")
    get_credentials_path().write_text("")

    with pytest.raises(CredentialReadError):
        design.use(switcher, "personal")


def test_rotate_cycles_in_add_order(switcher):
    set_live({"refreshToken": "a"})
    design.add(switcher, "a")
    assert design.rotate(switcher) is None  # nothing else to go to
    set_live({"refreshToken": "b"})
    design.add(switcher, "b")

    assert design.rotate(switcher) == "a"
    assert design.rotate(switcher) == "b"
    assert live()["designOauth"] == {"refreshToken": "b"}


def test_remove_active_forgets_it_but_leaves_live(switcher):
    set_live({"refreshToken": "p1"})
    design.add(switcher, "personal")

    design.remove(switcher, "personal")

    assert stored(switcher, "personal") is None
    assert design.load_state(switcher) == ([], None)
    assert live()["designOauth"] == {"refreshToken": "p1"}


def test_switch_is_logged_for_the_history_menu(switcher, caplog):
    set_live({"refreshToken": "a"})
    design.add(switcher, "a")
    set_live({"refreshToken": "b"})
    design.add(switcher, "b")

    with caplog.at_level("INFO", logger="claude-swap"):
        design.use(switcher, "a")

    assert "Switched Design login from b to a" in caplog.text
