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
macpulse --report        # write an HTML report to the Desktop
macpulse --fix           # offer each fix one at a time
macpulse --fix --yes     # apply every safe fix without asking
macpulse --json          # machine-readable
macpulse --brief         # one line per warning, silent when healthy (for AI assistants)
macpulse --lang az|en|ru # default follows your system language
```

## Languages

Azerbaijani · English · Russian. Adding one means adding one dictionary to
`macpulse_strings.py` — the scanner never builds sentences, it carries message keys and
renders them at the end.

## What it will not do

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
