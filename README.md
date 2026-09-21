# Storeyes Device Agent

Runs on a Raspberry Pi. Every minute, it polls the admin panel backend for a pending Command and
reports back the exit code and log once it's done. There are two kinds of commands:

- **`RUN`** — the backend has already built the full shell string (from `Software.entrypoint` +
  `CommandStructure` arguments); the agent just executes `cmd` as-is.
- **`INSTALL`** — the backend only supplies the raw ingredients (`githubUrl`, `code`); the agent
  itself builds and runs the install sequence (see `src/installer.py`). Everything installs under
  `base_dir` from `config.conf` (default `/home/m0hcine24`). If `<base_dir>/<code>` already
  exists, it skips straight to success (treated as already installed) rather than attempting a
  `git clone` that would fail on a non-empty directory. Otherwise:
  1. `git clone <githubUrl> <base_dir>/<code>`
  2. `cd <base_dir>/<code>`
  3. `chmod +x install.sh`
  4. `sudo ./install.sh`

  These are chained in one shell invocation so `cd` carries over and the sequence stops at the
  first failing step. Whatever exit code comes out of that chain is reported back the same way as
  any other command; the backend flips the linked `Installation` to `INSTALLED` on success (or
  `FAILED` otherwise) — see `CommandPollingService.recordResult`.

  Note: this means **Reinstall is currently a no-op** once `<base_dir>/<code>` exists — it just
  re-reports success without re-cloning or re-running `install.sh`. Say if you want Reinstall to
  actually wipe and redo it.

## Running as root, rooted at `base_dir`

The agent runs as root (it has to — installs call `apt`, write to `/etc`, and so on), but every
command it executes runs **from `base_dir` with `HOME=base_dir`**, not from `/root`. That's set in
two places: `install.sh` puts `HOME=<base_dir>` at the top of the cron.d entry, and
`src/executor.py` passes `cwd`/`HOME` per command. So the backend's `RUN` commands, which `cd
~/<code>` (see `CommandBuilderService`), land in the same place `INSTALL` cloned to.

A relative command therefore resolves against `base_dir`. If `base_dir` doesn't exist the agent
still polls normally — only the commands themselves fail, and they report that back to the panel.

## Install

```bash
sudo ./install.sh --base-url https://panel.storeyes.io/api --base-dir /home/m0hcine24
```

This installs the `at` package (required for `longRunning` commands, which the backend wraps as
`echo '<cmd>' | at now` so a never-exiting process doesn't block the once-a-minute poll loop),
writes `/etc/cron.d/storeyes-agent` to run it every minute, and adds a `logrotate` entry for
`/var/log/storeyes-agent.log`.

The agent runs from wherever this repository is checked out — `install.sh` copies nothing, it just
points cron at `main.py` in place. Shipping a code update is therefore a `git pull` in this
directory; re-run `install.sh` only if the checkout moves. Re-running it never overwrites an
existing `config.conf` — an existing one's `base_dir` also wins over `--base-dir`, and the cron
entry's `HOME` is written from whatever that file ends up saying.

## Identity

The agent has no device-specific config to fill in. It identifies itself to the backend using
this Raspberry Pi's own hardware serial number (`/proc/cpuinfo`), sent as the `X-DEVICE-ID`
header — the same header every other device-gw endpoint in this backend already expects. The end
of `install.sh` prints this serial — create (or confirm) a `Device` row with that exact value as
its `boardId` in the admin panel. No API key is used for now (the backend accepts a `Device` with
`apiKey = null`, matched by `boardId` alone).

## Files

- `main.py` — entry point; one poll/execute/report pass per invocation, branches on `type`.
- `src/device_identity.py` — reads the Pi's serial from `/proc/cpuinfo`.
- `src/api_client.py` — `GET /device-gw/commands/next`, `POST /device-gw/commands/{id}/result` (stdlib `urllib` only — no `pip install` needed).
- `src/installer.py` — builds and runs the `INSTALL` step sequence from `githubUrl`/`code`.
- `src/executor.py` — runs a shell command via `subprocess` from `base_dir` with `HOME=base_dir`, capturing exit code + combined stdout/stderr. Used directly for `RUN` commands, and by `installer.py` for `INSTALL`.
- `src/config.py` — loads `config.conf` (`base_url`, `timeout_seconds`, `max_log_chars`, `base_dir`).

## Why cron, not a daemon

A command still `RUNNING` when the next minute's tick fires isn't a problem: the backend only
hands out a command still in `PENDING` status, so an overlapping tick just gets "nothing to do"
(204) and exits immediately. No lock file, no process supervisor needed.

This agent is otherwise independent of
[storeyes-onboarding](https://github.com/storeyescoffee/storeyes-onboarding) — that's a separate,
unrelated service that happens to run on the same Pi. Neither one triggers or depends on the
other; storeyes-fast-onboarding's Software tab installs this agent directly over SSH instead.
