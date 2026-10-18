# macpulse

**Your Mac isn't slow because the disk is full — but it can still be stopped by it.**

Every Mac cleaner measures the same thing: disk space. Caches, logs, language files,
"junk". That model was built for a Mac whose problem was a full drive, and it is blind
to what actually slows a modern developer's machine down.

macpulse measures **live waste** — what is running right now and what it costs you.

```
curl -fsSL https://raw.githubusercontent.com/AlimAlirzayev/macpulse/main/install.sh | bash
```

No admin rights. Nothing installed outside your home folder. Read-only until you press Fix.

---

## What it finds that a disk cleaner cannot

| | |
|---|---|
| **CPU burners** | Processes that have held a core for days, ranked by core-hours. The one that broke the Mac this was written on used **300 KB of memory** — bottom of any size-sorted list — while pinning a core at 145% for six days. |
| **Ghost processes** | Still running from an app you deleted, or a disk image no longer mounted. Their uninstaller left with the app, so no disk cleanup will ever reach them. |
| **AI session multiplication** | Every Claude Code / Cursor tab starts its **own** MCP server stack. Ten tabs is 3–5 GB of duplicated infrastructure that never shows up in Activity Monitor as one line. |
| **Dead MCP servers** | Configured but failing auth. macpulse calls the endpoint instead of trusting the config file. |
| **Headless browser leftovers** | Chrome instances abandoned by automation scripts, sometimes running for days. |
| **Stale lock files** | The reason an app silently refuses to launch (error `-1712`). |
| **Idle Docker** | A Linux VM kept alive with zero containers running. |
| **Swap saturation** | Measured against your RAM, not as a share of a swap file macOS grows on demand — the percentage version calls a Mac with 8 GB in swap "80% full" and healthy. |
| **Disk headroom** | Memory spills onto the disk, so a full disk is a memory failure waiting to happen: that is the "your system has run out of application memory" dialog. Warns while there is still room to act, and can reclaim caches, build products and the Trash. |
| **Where the disk is heading** | Free space trends. Losing a gigabyte a day means a date with the same wall, said a week early. |
| **Memory hogs** | Per-app footprint the way the Force Quit window measures it — `ps` hides compressed and swapped pages, which for a browser open all week is most of it. One press quits the app and brings it back. |

## How it looks

A live score in the menu bar, with swap and free disk under it. Click it for findings,
each with **how many days it has been true** — the thing a single scan can never tell you.

Between full scans a sentinel reads two kernel counters every minute, so the moment
memory starts spilling onto a disk that cannot take it, you hear about it — once, with
the reason and what to do, not on every scan.

`Open panel…` gives a fuller view laid out like System Settings, with a Fix button on
each finding.

## Commands

```
macpulse                 # scan, score out of 100, ranked findings
macpulse --ui            # open the panel
macpulse --report        # write an HTML report (see 'Report location' below)
macpulse --fix           # offer each fix one at a time
macpulse --fix --yes     # apply every safe fix without asking
macpulse --json          # machine-readable
macpulse --brief         # one line per warning, silent when healthy (for AI assistants)
macpulse --lang az|en|ru # default follows your system language
macpulse --exit-status   # exit 0 healthy, 1 warn, 2 critical (for scripts and monitors)
macpulse --metrics       # Prometheus/OpenMetrics text
macpulse --doctor        # check macpulse's own installation (add --json for machine output)
macpulse --mcp           # read-only MCP server on stdio
```

Report location: `--report` never writes to the Desktop. It uses `$MACPULSE_REPORT_DIR`
if set, else `~/Documents/OS-Output` if that folder exists, else `~/Documents/macpulse`.

## What's new in 1.4

- **Explainable score.** `--json` carries `score_breakdown`, a list of
  `{key, reason, points}`; `100 - sum(points)`, clamped to 0-100, is the score. The
  terminal report prints a one-line "why this score". Findings with one root cause
  (swap pressure and per-app memory hogs) share a combined cap of 30 points instead of
  being counted once each.
- **Kernel signals.** Memory pressure level (`kern.memorystatus_vm_pressure_level`),
  thermal throttling (`pmset -g therm`) and battery health (`ioreg AppleSmartBattery`)
  appear under `memory` in `--json`. Throttling or a battery below 80% capacity raises a
  warning; a healthy or absent battery stays silent.
- **Check coverage.** `--json` has `checks: {run, failed}`: a check that raises is
  listed, not silently dropped.
- **`--exit-status`.** Nagios convention: 0 no warn/critical, 1 worst is warn,
  2 worst is critical. Without the flag every mode still exits 0, so the SessionStart
  `--brief` hook behaves as before.
- **`--metrics`.** `macpulse_score`, `macpulse_swap_used_bytes`,
  `macpulse_memory_pressure_level` and `macpulse_findings{severity=...}` with `# HELP` /
  `# TYPE` lines, terminated by `# EOF`. It prints text on demand; there is no exporter
  daemon, so point a textfile collector or cron job at it.
- **`--doctor`.** One OK/WARN/FAIL line per check: CLI version against the app bundle,
  the `io.macpulse.agent` LaunchAgent loaded with a live pid, history DB
  `PRAGMA integrity_check`, installed files against the repo copies, and the
  `macpulse --brief` hook in `~/.claude/settings.json`. Exit 1 only on FAIL.
- **`--mcp`.** A minimal MCP server (newline-delimited JSON-RPC over stdio) with two
  read-only tools, `scan` and `explain_score`. No tool can fix, quit, kill or delete
  anything, and nothing registers it for you. Optional, if you want Claude Code to call it:

  ```
  claude mcp add macpulse -- ~/.local/bin/macpulse --mcp
  ```

- **AI session age.** The Claude Code finding shows how long each session has been up.

## 1.5.3

- The menu bar agent keeps only numeric `memory` values, so no field of the CLI's JSON can crash it.

## 1.5.2

- A Claude Code session whose child process (a build, a test run) is busy is no longer treated as idle.
- The menu bar agent drops finding fields of the wrong type instead of crashing on them.
- The process-tree walk is cycle-safe (a self-parented pid could hang a scan).

## 1.5.1 (fixes from the release review)

- A scan whose swap sensor failed no longer records 0 GB, so the next scan cannot raise a false swap-growth warning.
- `install.sh` verifies `menubar.m` on the local-copy path too (it is compiled into the login agent).
- The menu bar agent no longer crashes on JSON `null` values.
- Idle-session selection now ignores sessions busy at scan time and processes that only carry a `.../claude` path. The stop button re-checks each PID's command before it sends SIGTERM, so a recycled PID is never signalled.

## What's new in 1.5

- **Honest menu bar.** When a scan could not measure everything (`"complete": false` in
  `--json`), the title shows `◍ 100?` and the menu names what was skipped. The menu also
  shows the largest score deduction. `MACPULSE_BIN` points the agent at another CLI, and
  `macpulse-menubar --print-title` prints the title it would show and exits.
- **Idle AI sessions.** A Claude Code session open 12 h or more that has used under 0.5%
  of a core over its lifetime is reported as `ai:idle`, never the session running the scan.
  Its fix sends SIGTERM to exactly those PIDs, and it is excluded from `--fix --yes` and
  the panel's "fix all" (`auto_fix: false` in `--json`): you stop sessions on purpose.
- **Swap growth.** A warning when swap used grew by 1 GiB or more within 30 minutes,
  judged from the scan history.
- **Verifiable release.** `release.sh` writes `SHA256SUMS` (committed) and a CycloneDX 1.5
  `sbom.cdx.json` (a release asset, no dependencies). When `install.sh` downloads, it
  fetches `SHA256SUMS`, checks every file in a staging folder and installs nothing on a
  mismatch or if the list is missing.

Honest limit: releases are checksummed and carry an SBOM, but they are **not
Apple-notarized or code-signed**; that needs a paid Developer ID. A checksum shows the files
match the published list. It does not prove who published the list. The menu bar app is
built on your machine for the same reason as before, so Gatekeeper does not apply to it.

### Tests

```
python3 -m unittest discover -s tests
```

Offline, stdlib only, a few seconds. A few tests compile `menubar.m` (skipped without
`clang`) and run `install.sh` against a sandbox HOME. They exercise pure functions on fixtures
(including a replay of the incident this tool was built after: 8 GB RAM, 8.4 GB of swap,
306 MB of disk free) and drive the MCP server in-process. They do not run a live scan,
so they cannot catch a regression that only shows up against a real machine's
`vm_stat` or `ps` output.

## Languages

Azerbaijani · English · Russian. Adding one means adding one dictionary to
`macpulse_strings.py` — the scanner never builds sentences, it carries message keys and
renders them at the end.

## What it will not do

The MCP server and metrics output are deliberately small: no authentication, no
network listener, no write tools. The thermal and battery readings depend on what
`pmset` and `ioreg` report on your hardware and may be empty on some Macs.

It will not claim to turn an 8 GB Mac into a 16 GB one. It does not touch your files or
your disk. It reads the process table, `vm_stat`, swap, and a handful of lock files —
that is the whole surface.

"Recoverable" only counts what pressing Fix would actually free. Reporting your normal
Chrome helper processes as reclaimable would be the same overclaim this tool exists to
argue against.

## Requirements

macOS 12+, Python 3.9+ (ships with the Xcode Command Line Tools). No pip packages, no
daemon, no account, no telemetry.

## How the install works, and why

The `.app` is **built on your machine**, not downloaded prebuilt. A downloaded unsigned
app is quarantined and Gatekeeper refuses it outright — avoiding that normally costs a
paid Apple Developer ID and notarisation. A locally assembled bundle is never
quarantined, so it just works.

The menu bar agent is Objective-C compiled by `clang` at install time. Swift was tried
first and rejected for distribution: on a Command Line Tools-only Mac, `swiftc` can fail
to compile even `print("hi")` against its own SDK. If no compiler is present at all, the
installer degrades to a panel-only app rather than failing.

## Uninstall

```
rm -rf ~/Applications/macpulse.app ~/.local/bin/macpulse* \
       ~/Library/Application\ Support/macpulse
```

## License

MIT © Alim Alirzayev
