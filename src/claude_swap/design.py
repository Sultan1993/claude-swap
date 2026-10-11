"""Claude Design logins, switched independently of the Claude Code login.

Claude Code keeps the ``/design-login`` credential as ``designOauth`` beside the
login in one credential object and never checks it against that login, so any
saved design login can be live while the Code accounts rotate underneath.

Tokens live in the regular backup store (Keychain on macOS, ``.enc`` files
elsewhere) under the pseudo-slot ``design``; ``design.json`` in the backup dir
holds the names in add order and the active one. Saving a design login turns
``swap.designLogin`` off, so Code switches leave the live one alone.
"""

from __future__ import annotations

import json
import re
from contextlib import contextmanager

from claude_swap.claude_locks import (
    CREDENTIALS_STALENESS_S,
    claude_config_lock,
    claude_credentials_lock,
    design_refresh_lock_dir,
    proper_lockfile,
)
from claude_swap.credentials import DESIGN_CREDENTIAL_KEY
from claude_swap.exceptions import (
    AccountNotFoundError,
    CredentialReadError,
    ValidationError,
)
from claude_swap.locking import FileLock
from claude_swap.settings import set_setting

_SLOT = "design"
_NAME_RE = re.compile(r"^[A-Za-z0-9._@+-]{1,64}$")


def load_state(switcher) -> tuple[list[str], str | None]:
    """Saved design login names (add order) and the active one, if any."""
    data = switcher._read_json(switcher.backup_dir / "design.json") or {}
    names = [n for n in data.get("names", []) if isinstance(n, str)]
    active = data.get("active")
    return names, active if active in names else None


def _save_state(switcher, names: list[str], active: str | None) -> None:
    switcher._write_json(
        switcher.backup_dir / "design.json", {"names": names, "active": active}
    )


@contextmanager
def _locked(switcher):
    # Claude Code refreshes designOauth under its own lock and writes it back
    # compare-and-swap, so hold that one too — plus everything a Code switch
    # holds, so the two never interleave on the shared credential object.
    with (
        proper_lockfile(
            design_refresh_lock_dir(), staleness=CREDENTIALS_STALENESS_S
        ),
        FileLock(switcher.lock_file),
        claude_credentials_lock(),
        claude_config_lock(),
    ):
        yield


def _read_live(switcher) -> dict:
    active = switcher._read_active_credentials()
    if active.degraded:
        raise CredentialReadError(
            "The macOS Keychain is unreadable right now; retry from a GUI session"
        )
    try:
        data = json.loads(active.value or "")
    except json.JSONDecodeError:
        data = None
    if not isinstance(data, dict) or "claudeAiOauth" not in data:
        raise CredentialReadError(
            "No Claude Code login is active; the Design login lives beside it"
        )
    return data


def _save_back(switcher, live: dict, active: str | None) -> None:
    # The live copy is the freshest generation of the active login (Claude Code
    # rotates its refresh token), so it goes back to the store before anything
    # replaces it.
    # ponytail: the token carries no account id, so a /design-login that was
    # never added is saved over the active name; `add` it first.
    if active and live.get(DESIGN_CREDENTIAL_KEY):
        switcher._store._write_account_credentials(
            _SLOT, active, json.dumps(live[DESIGN_CREDENTIAL_KEY])
        )


def add(switcher, name: str) -> None:
    """Save the live design login as ``name`` (replacing it) and mark it active."""
    if not _NAME_RE.match(name):
        raise ValidationError(
            "Design login names are 1-64 letters, digits or . _ @ + -"
        )
    with _locked(switcher):
        login = _read_live(switcher).get(DESIGN_CREDENTIAL_KEY)
        if not login:
            raise CredentialReadError(
                "No Claude Design login is live; run /design-login in Claude Code first"
            )
        switcher._store._write_account_credentials(_SLOT, name, json.dumps(login))
        names, _ = load_state(switcher)
        if name not in names:
            names.append(name)
        _save_state(switcher, names, name)
    set_setting(switcher.backup_dir, "swap.designLogin", "false")


def use(switcher, name: str) -> bool:
    """Make ``name`` the live design login. False when it already is."""
    with _locked(switcher):
        names, active = load_state(switcher)
        if name not in names:
            raise AccountNotFoundError(f"No saved Design login named {name!r}")
        if name == active:
            return False
        stored = switcher._store._read_account_credentials(_SLOT, name)
        if not stored:
            raise CredentialReadError(
                f"The saved Design login {name!r} is unreadable; add it again"
            )
        live = _read_live(switcher)
        _save_back(switcher, live, active)
        live[DESIGN_CREDENTIAL_KEY] = json.loads(stored)
        switcher._write_credentials(json.dumps(live))
        _save_state(switcher, names, name)
    switcher._logger.info(f"Switched Design login from {active or 'none'} to {name}")
    return True


def rotate(switcher) -> str | None:
    """Switch to the next saved design login; returns it (None if there is none)."""
    names, active = load_state(switcher)
    if not names or names == [active]:
        return None
    nxt = names[(names.index(active) + 1) % len(names)] if active else names[0]
    use(switcher, nxt)
    return nxt


def remove(switcher, name: str) -> None:
    """Forget a saved design login. The live one stays put if it was active."""
    with _locked(switcher):
        names, active = load_state(switcher)
        if name not in names:
            raise AccountNotFoundError(f"No saved Design login named {name!r}")
        switcher._store._delete_account_credentials(_SLOT, name)
        names.remove(name)
        _save_state(switcher, names, None if name == active else active)
