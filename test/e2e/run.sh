#!/bin/sh
# Starts a private fcitx5 with one of our input methods selected, on its own
# D-Bus session and its own config, then types at it. Touches nothing belonging
# to the fcitx5 the user is actually running.
#
# Usage: run.sh [input-method-name]      default: mulga
#   mulga           the C++ addon
#   m17n_uz_Mulga   the .mim, through fcitx5-m17n
set -e

here=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
im="${1:-${MULGA_IM:-mulga}}"
driver="${MULGA_DRIVER:-$here/drive.py}"
fcitx5_bin="${MULGA_FCITX5:-fcitx5}"

# m17n reads its user directory from M17NDIR, so the .mim needs no install.
# Works both from a checkout and from the copy staged into the nix store.
if [ -z "${M17NDIR:-}" ]; then
  if [ -d "$here/../../m17n" ]; then
    M17NDIR=$(CDPATH= cd -- "$here/../../m17n" && pwd)
  elif [ -d "$here/m17n" ]; then
    M17NDIR="$here/m17n"
  fi
fi
export M17NDIR

# The conformance corpus, shared with the macOS layout checker.
if [ -z "${MULGA_CORPUS:-}" ]; then
  if [ -f "$here/../../spec/corpus.tsv" ]; then
    MULGA_CORPUS=$(CDPATH= cd -- "$here/../../spec" && pwd)/corpus.tsv
  elif [ -f "$here/corpus.tsv" ]; then
    MULGA_CORPUS="$here/corpus.tsv"
  fi
fi
export MULGA_CORPUS

tmp=$(mktemp -d)
trap 'rm -rf "$tmp"' EXIT

export XDG_CONFIG_HOME="$tmp/config"
export XDG_DATA_HOME="$tmp/data"
export XDG_CACHE_HOME="$tmp/cache"
export XDG_RUNTIME_DIR="$tmp/run"
mkdir -p "$XDG_CONFIG_HOME/fcitx5" "$XDG_DATA_HOME" "$XDG_CACHE_HOME" "$XDG_RUNTIME_DIR"

# fcitx5 will not pick a uz input method for a us layout on its own, so say so.
cat > "$XDG_CONFIG_HOME/fcitx5/profile" <<PROFILE
[Groups/0]
Name=Default
Default Layout=us
DefaultIM=$im

[Groups/0/Items/0]
Name=$im
Layout=

[GroupOrder]
0=Default
PROFILE

# No display here, so the frontends and UI that want one are left out.
unset DISPLAY WAYLAND_DISPLAY

exec dbus-run-session -- sh -c '
  "$1" -D -k \
    --disable=xcb,wayland,classicui,kimpanel,notificationitem,virtualkeyboard \
    --verbose="default=2" >"$3/fcitx.log" 2>&1 &
  fcitx_pid=$!
  MULGA_IM="$4" python3 "$2"
  status=$?
  kill $fcitx_pid 2>/dev/null || true
  exit $status
' sh "$fcitx5_bin" "$driver" "$tmp" "$im"
