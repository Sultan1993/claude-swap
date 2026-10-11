# claude-swap (Claude Design fork)

A fork of [realiti4/claude-swap](https://github.com/realiti4/claude-swap), kept on top of its `main`, that adds Claude Design login switching. For installation, usage and everything else, see the original repo.

## What this fork adds

- **One Claude Design login kept across Code switches.** Upstream PR [#349](https://github.com/realiti4/claude-swap/pull/349) (`swap.designLogin`): a Claude Code account switch no longer drops your `/design-login`.
- **Claude Design logins switched on their own.** `cswap design add|use|next|remove` saves several design logins and puts any one of them live, whichever Code account is active.
- **Reorganised menu bar.** Code accounts at the top with a *Switch* submenu; a *Claude Design: &lt;name&gt;* submenu; add, remove and disable for both under *Manage accounts*; one switch history with each entry tagged *Code* or *Design*.
- **Refresh fix.** When cswap refreshes or restores the active account from its backup, it keeps the live `mcpOAuth` and design login instead of putting the slot's stale copies back.

## Install

```bash
pipx install --force 'claude-swap[menubar] @ git+https://github.com/Sultan1993/claude-swap'
# or: uv tool install --force 'claude-swap[menubar] @ git+https://github.com/Sultan1993/claude-swap'
launchctl kickstart -k gui/$(id -u)/com.cswap.menubar   # if the menu bar runs as a service
```

`cswap upgrade` installs the original from PyPI and replaces the fork, so update with the command above instead.

## Switch Claude Design logins

```bash
# in Claude Code: /design-login, pick the account in the browser, then
cswap design add personal       # save the live design login as 'personal'
cswap design                    # list; * marks the live one
cswap design use work
cswap design next               # rotate to the next saved login
cswap design remove work
```

The menu bar has the same under *Claude Design* and *Manage accounts → Claude Design*. Saving a design login sets `swap.designLogin` to `false`, so Code switches leave the live one in place.

- **Add before you switch.** A design token carries no account id, so cswap cannot tell a new `/design-login` from a refreshed one: the live token is saved back to the active name before each switch. After a `/design-login`, run `cswap design add` first.
- **`/login` and `/logout` revoke the live one.** Claude Code revokes the design login whenever you log in or out. Add your Code accounts first, and after a re-login run `/design-login` again and `cswap design add` it under the same name. The other saved logins are separate grants and keep working.

## Only one design login?

Skip `cswap design` and just keep it across Code switches:

```bash
cswap config set swap.designLogin false
```

Then run `/design-login` once, from any account.
