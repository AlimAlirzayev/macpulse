#!/bin/bash
# macpulse installer — one command, no admin rights, no dependencies.
#
#   curl -fsSL <url>/install.sh | bash
#
# Design notes for whoever maintains this:
#
# * The .app bundle is BUILT ON THE USER'S MACHINE rather than shipped prebuilt.
#   A downloaded .app carries a quarantine attribute and, unsigned, Gatekeeper
#   refuses it outright ("damaged and can't be opened") — which would need a paid
#   Apple Developer ID and notarisation to avoid. An app assembled locally from
#   plain scripts is never quarantined, so it just works. This is the whole reason
#   the installer looks like this.
# * Nothing is installed outside the user's home directory, so no sudo is needed
#   and an uninstall is a single rm.
# * The tool adapts to the machine it lands on: it reads RAM, CPU count, swap and
#   the system language at runtime, so no per-machine configuration exists.

set -euo pipefail

BIN="$HOME/.local/bin"
APPDIR="$HOME/Applications"
APP="$APPDIR/macpulse.app"
PORT=7745

c_ok=$'\033[32m'; c_dim=$'\033[2m'; c_b=$'\033[1m'; c_r=$'\033[0m'; c_err=$'\033[31m'
say()  { printf '  %s\n' "$*"; }
ok()   { printf '  %s✓%s %s\n' "$c_ok" "$c_r" "$*"; }
die()  { printf '  %s✗ %s%s\n' "$c_err" "$*" "$c_r" >&2; exit 1; }

printf '\n  %smacpulse%s installer\n\n' "$c_b" "$c_r"

# ---------------------------------------------------------------- preflight
[ "$(uname -s)" = "Darwin" ] || die "macpulse only runs on macOS."

MACOS=$(sw_vers -productVersion 2>/dev/null || echo "0")
MAJOR=${MACOS%%.*}
[ "${MAJOR:-0}" -ge 12 ] 2>/dev/null || die "macOS 12 or newer is required (found $MACOS)."

# Python 3.9+ — every supported macOS ships python3 via the Command Line Tools, but
# on a machine where they were never installed, `python3` is a stub that opens a
# dialog. Test that it actually runs before relying on it.
PY=""
for cand in /opt/homebrew/bin/python3 /usr/local/bin/python3 "$(command -v python3 || true)" /usr/bin/python3; do
  [ -n "$cand" ] && [ -x "$cand" ] || continue
  if "$cand" -c 'import sys; raise SystemExit(0 if sys.version_info>=(3,9) else 1)' 2>/dev/null; then
    PY="$cand"; break
  fi
done
[ -n "$PY" ] || die "Python 3.9+ not found. Install it with: xcode-select --install"

ARCH=$(uname -m)
RAM_GB=$(( $(sysctl -n hw.memsize) / 1073741824 ))
ok "macOS $MACOS · $ARCH · ${RAM_GB} GB RAM · $("$PY" -V 2>&1)"

# ---------------------------------------------------------------- fetch
# The program files sit next to this script. When piped from curl, $0 is "bash",
# so fall back to downloading them from the same base URL the installer came from.
BASE="${MACPULSE_BASE:-https://raw.githubusercontent.com/AlimAlirzayev/macpulse/main}"
SRC_DIR=""
# An explicit MACPULSE_BASE means "install from there": it wins over the files that sit
# next to this script, so the verified download path cannot be bypassed by accident.
if [ -z "${MACPULSE_BASE:-}" ] && [ -f "${BASH_SOURCE[0]:-}" ]; then
  SRC_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
  [ -f "$SRC_DIR/macpulse" ] || SRC_DIR=""
fi

PROGRAM_FILES="macpulse macpulse_strings.py macpulse_history.py macpulse_doctor.py macpulse_mcp.py"
STAGE=""
STAGED_MENUBAR=""
cleanup() { [ -z "$STAGE" ] || rm -rf "$STAGE"; }
trap cleanup EXIT

if [ -n "$SRC_DIR" ]; then
  # A local copy is held to the same standard when it ships a SHA256SUMS: an unpacked
  # release with one altered file must not install. A developer tree without the file
  # (or with MACPULSE_DEV=1 while editing) installs as-is.
  if [ -f "$SRC_DIR/SHA256SUMS" ] && [ "${MACPULSE_DEV:-0}" != "1" ]; then
    # menubar.m is compiled into the login agent, so it is verified like the rest.
    LOCAL_VERIFY="$PROGRAM_FILES"; [ -f "$SRC_DIR/menubar.m" ] && LOCAL_VERIFY="$PROGRAM_FILES menubar.m"
    for f in $LOCAL_VERIFY; do
      awk -v f="$f" '$2 == f || $2 == "*" f' "$SRC_DIR/SHA256SUMS" | grep -q . \
        || die "$f is not listed in SHA256SUMS — nothing was installed"
    done
    (cd "$SRC_DIR" && for f in $LOCAL_VERIFY; do
       awk -v f="$f" '$2 == f || $2 == "*" f' SHA256SUMS; done | shasum -a 256 -c - >/dev/null 2>&1) \
      || die "checksum mismatch against SHA256SUMS — nothing was installed (run release.sh after editing)"
    ok "checksums verified (local copy)"
  fi
  mkdir -p "$BIN" "$APPDIR"
  for f in $PROGRAM_FILES; do cp "$SRC_DIR/$f" "$BIN/"; done
  ok "installed from $SRC_DIR"
elif [ -n "$BASE" ]; then
  # Verified install: every file is downloaded into a staging directory and checked
  # against SHA256SUMS BEFORE anything is copied into $HOME. A mismatch, a file missing
  # from the list, or no SHA256SUMS at all aborts with nothing installed. This protects
  # against a corrupted or tampered download; it is not a signature (see README).
  STAGE="$(mktemp -d)"
  curl -fsSL "$BASE/SHA256SUMS" -o "$STAGE/SHA256SUMS" \
    || die "could not download SHA256SUMS from $BASE — refusing to install unverified files"
  for f in $PROGRAM_FILES; do
    curl -fsSL "$BASE/$f" -o "$STAGE/$f" || die "could not download $f from $BASE"
  done
  # The menu bar source is optional (no compiler means no agent), but if it is fetched
  # it is verified like everything else.
  if curl -fsSL "$BASE/menubar.m" -o "$STAGE/menubar.m" 2>/dev/null; then
    STAGED_MENUBAR="$STAGE/menubar.m"
    VERIFY_FILES="$PROGRAM_FILES menubar.m"
  else
    VERIFY_FILES="$PROGRAM_FILES"
  fi
  : > "$STAGE/subset"
  for f in $VERIFY_FILES; do
    awk -v f="$f" '$2 == f || $2 == "*" f' "$STAGE/SHA256SUMS" | grep . >> "$STAGE/subset" \
      || die "$f is not listed in SHA256SUMS — nothing was installed"
  done
  (cd "$STAGE" && shasum -a 256 -c subset >/dev/null 2>&1) \
    || die "checksum mismatch against SHA256SUMS — nothing was installed"
  ok "checksums verified ($(echo $VERIFY_FILES | wc -w | tr -d ' ') files)"
  mkdir -p "$BIN" "$APPDIR"
  for f in $PROGRAM_FILES; do cp "$STAGE/$f" "$BIN/$f"; done
  ok "installed from $BASE"
else
  die "No source found and MACPULSE_BASE is unset."
fi
chmod +x "$BIN/macpulse"

"$PY" -c "import ast,sys; ast.parse(open('$BIN/macpulse').read())" \
  || die "the downloaded file is not valid Python — aborting rather than installing something broken"

# ---------------------------------------------------------------- app bundle
rm -rf "$APP"
mkdir -p "$APP/Contents/MacOS" "$APP/Contents/Resources"

cat > "$APP/Contents/Info.plist" <<PLIST
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>CFBundleName</key><string>macpulse</string>
  <key>CFBundleDisplayName</key><string>macpulse</string>
  <key>CFBundleIdentifier</key><string>io.macpulse.app</string>
  <key>CFBundleVersion</key><string>1.5.2</string>
  <key>CFBundleShortVersionString</key><string>1.5.2</string>
  <key>CFBundlePackageType</key><string>APPL</string>
  <key>CFBundleExecutable</key><string>macpulse</string>
  <key>CFBundleIconFile</key><string>macpulse</string>
  <key>LSMinimumSystemVersion</key><string>12.0</string>
  <key>LSUIElement</key><true/>
  <key>NSHighResolutionCapable</key><true/>
</dict>
</plist>
PLIST

# The menu bar agent is compiled here, on this machine. That is what keeps the app
# out of Gatekeeper's way — a locally built binary is never quarantined, so no Apple
# Developer ID or notarisation is needed. Objective-C rather than Swift on purpose:
# swiftc on a Command Line Tools-only Mac frequently cannot build against its own SDK,
# while clang has no equivalent failure mode.
MENUBAR_SRC=""
if [ -n "$SRC_DIR" ] && [ -f "$SRC_DIR/menubar.m" ]; then
  MENUBAR_SRC="$SRC_DIR/menubar.m"
elif [ -n "$STAGED_MENUBAR" ]; then
  MENUBAR_SRC="$STAGED_MENUBAR"
fi

MENUBAR_OK=0
if [ -n "$MENUBAR_SRC" ] && command -v clang >/dev/null 2>&1; then
  if clang -fobjc-arc -O2 -mmacosx-version-min=12.0 -framework AppKit \
       -o "$APP/Contents/MacOS/macpulse" "$MENUBAR_SRC" 2>/dev/null; then
    MENUBAR_OK=1
    ok "menu bar agent compiled"
  fi
fi

# Without a compiler the app still works — it just opens the panel directly instead of
# living in the menu bar. Degrading is better than failing to install.
if [ "$MENUBAR_OK" -eq 0 ]; then
  cat > "$APP/Contents/MacOS/macpulse" <<LAUNCH
#!/bin/bash
export PATH="\$HOME/.local/bin:/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin"
exec "$PY" "\$HOME/.local/bin/macpulse" --ui --port $PORT
LAUNCH
  say "${c_dim}no compiler found — installing the panel-only app${c_r}"
fi
chmod +x "$APP/Contents/MacOS/macpulse"

# The icon is drawn here rather than downloaded, so the install has no binary assets
# to verify and works even if only the scripts made it across.
"$PY" - "$APP/Contents/Resources/icon.png" <<'PYICON'
import math, pathlib, struct, sys, zlib
N=512; BG=(0x0B,0x1B,0x21),(0x05,0x0F,0x13); TEAL=(0x35,0xD6,0xC8)
R=N*0.0165; CORNER=int(N*0.225)
def ty(x):
    t=((x/N)*1.45+0.42)%1.0
    if   t<0.14: v=math.sin(t/0.14*math.pi)*0.11
    elif t<0.22: v=-0.10*math.sin((t-0.14)/0.08*math.pi)
    elif t<0.30: v=math.sin((t-0.22)/0.08*math.pi)
    elif t<0.40: v=-0.30*math.sin((t-0.30)/0.10*math.pi)
    elif t<0.62: v=math.sin((t-0.40)/0.22*math.pi)*0.19
    else: v=0.0
    return N*0.50-v*N*0.30
cov=[0.0]*(N*N); ro=R+1.0; span=int(math.ceil(ro))
for i in range(N*6+1):
    cx=i*N/(N*6); cy=ty(cx)
    for py in range(max(0,int(cy-span)),min(N,int(cy+span)+1)):
        dy2=(py+0.5-cy)**2; base=py*N
        for px in range(max(0,int(cx-span)),min(N,int(cx+span)+1)):
            d=math.sqrt((px+0.5-cx)**2+dy2)
            if d>=ro: continue
            a=1.0 if d<=R else (ro-d)/(ro-R)
            if a>cov[base+px]: cov[base+px]=a
def shape(x,y):
    cx=min(max(x,CORNER),N-CORNER); cy=min(max(y,CORNER),N-CORNER)
    d=math.hypot(x-cx,y-cy)
    if d<=CORNER-0.7: return 1.0
    if d>=CORNER+0.7: return 0.0
    return (CORNER+0.7-d)/1.4
rows=[]
for y in range(N):
    row=bytearray(); f=y/N; base=y*N
    bg=tuple(int(BG[0][i]+(BG[1][i]-BG[0][i])*f) for i in range(3))
    for x in range(N):
        s=shape(x+0.5,y+0.5)
        if s<=0: row+=b'\x00\x00\x00\x00'; continue
        a=cov[base+x]
        row+=bytes(int(bg[i]+(TEAL[i]-bg[i])*a) for i in range(3))+bytes([int(255*s)])
    rows.append(bytes(row))
raw=b''.join(b'\x00'+r for r in rows)
ch=lambda tag,d: struct.pack('>I',len(d))+tag+d+struct.pack('>I',zlib.crc32(tag+d)&0xffffffff)
pathlib.Path(sys.argv[1]).write_bytes(
    b'\x89PNG\r\n\x1a\n'+ch(b'IHDR',struct.pack('>IIBBBBB',N,N,8,6,0,0,0))
    +ch(b'IDAT',zlib.compress(raw,9))+ch(b'IEND',b''))
PYICON

# iconutil ships with macOS but only inside the Command Line Tools; a PNG icon still
# works as a fallback, so a missing iconutil must not fail the install.
ICONSET=$(mktemp -d)/macpulse.iconset
mkdir -p "$ICONSET"
if command -v iconutil >/dev/null 2>&1 && command -v sips >/dev/null 2>&1; then
  for s in 16 32 128 256 512; do
    sips -z $s $s "$APP/Contents/Resources/icon.png" --out "$ICONSET/icon_${s}x${s}.png" >/dev/null 2>&1
    sips -z $((s*2)) $((s*2)) "$APP/Contents/Resources/icon.png" --out "$ICONSET/icon_${s}x${s}@2x.png" >/dev/null 2>&1
  done
  iconutil -c icns "$ICONSET" -o "$APP/Contents/Resources/macpulse.icns" 2>/dev/null \
    && rm -f "$APP/Contents/Resources/icon.png"
fi
rm -rf "$(dirname "$ICONSET")"
touch "$APP"
ok "app installed at ~/Applications/macpulse.app"

# ---------------------------------------------------------------- start at login
# A watcher that stops watching after a restart is not a watcher. The menu bar agent
# starts at login through a per-user LaunchAgent (no sudo, nothing outside $HOME).
# KeepAlive is off on purpose: choosing Quit from the menu must stay quit until the
# next login. The panel-only fallback is not started at login — it would open a
# browser window every time the Mac boots.
AGENT_PLIST="$HOME/Library/LaunchAgents/io.macpulse.agent.plist"
if [ "$MENUBAR_OK" -eq 1 ]; then
  mkdir -p "$HOME/Library/LaunchAgents"
  cat > "$AGENT_PLIST" <<PLIST
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>Label</key><string>io.macpulse.agent</string>
  <key>ProgramArguments</key>
  <array><string>$APP/Contents/MacOS/macpulse</string></array>
  <key>RunAtLoad</key><true/>
  <key>ProcessType</key><string>Background</string>
</dict>
</plist>
PLIST
  launchctl bootout "gui/$(id -u)/io.macpulse.agent" 2>/dev/null || true
  # bootout returns before launchd has finished tearing the old job down, and a
  # bootstrap issued in that window fails with "Input/output error". An upgrade then
  # leaves the menu bar watcher dead (measured on 1.3 -> 1.4), so retry briefly.
  for _ in 1 2 3 4 5 6 7 8 9 10; do
    launchctl bootstrap "gui/$(id -u)" "$AGENT_PLIST" 2>/dev/null && break
    launchctl print "gui/$(id -u)/io.macpulse.agent" >/dev/null 2>&1 && break
    sleep 0.5
  done
  # Check rather than assume: a malformed plist, or a background item the user has not
  # allowed under System Settings > General > Login Items, leaves nothing loaded.
  if launchctl print "gui/$(id -u)/io.macpulse.agent" >/dev/null 2>&1; then
    ok "starts at login (menu bar watcher, checks memory and disk every minute)"
  else
    say "${c_dim}could not register the login agent — allow macpulse under System Settings > General > Login Items${c_r}"
  fi
fi

# ---------------------------------------------------------------- PATH
SHELLRC="$HOME/.zshrc"; [ -n "${BASH_VERSION:-}" ] && [ ! -f "$SHELLRC" ] && SHELLRC="$HOME/.bash_profile"
if ! printf '%s' ":$PATH:" | grep -q ":$BIN:"; then
  if [ -f "$SHELLRC" ] && grep -q '\.local/bin' "$SHELLRC" 2>/dev/null; then
    :
  else
    printf '\n# added by the macpulse installer\nexport PATH="$HOME/.local/bin:$PATH"\n' >> "$SHELLRC"
    say "${c_dim}added ~/.local/bin to PATH in $(basename "$SHELLRC")${c_r}"
  fi
fi

# ---------------------------------------------------------------- verify
"$PY" "$BIN/macpulse" --version >/dev/null || die "installed, but the tool does not run."
ok "verified: $("$PY" "$BIN/macpulse" --version)"

printf '\n  %sDone.%s Open %smacpulse%s from Launchpad, or run:\n\n' "$c_b" "$c_r" "$c_b" "$c_r"
printf '      open -a macpulse          %s# the app%s\n' "$c_dim" "$c_r"
printf '      macpulse                  %s# terminal report%s\n' "$c_dim" "$c_r"
printf '      macpulse --lang ru        %s# az · en · ru%s\n\n' "$c_dim" "$c_r"
printf '  %sUninstall: launchctl bootout gui/$(id -u)/io.macpulse.agent; rm -rf ~/Applications/macpulse.app ~/Library/LaunchAgents/io.macpulse.agent.plist ~/.local/bin/macpulse*%s\n\n' "$c_dim" "$c_r"
