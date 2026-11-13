#!/usr/bin/env bash
# Install CPython 3.12.16 where uv finds managed interpreters (DECISIONS.md D1).
# uv 0.13.1's built-in download list predates the python-build-standalone release that has 3.12.16, so
# `uv python install 3.12.16` fails. This does the same thing by hand, with a pinned checksum.
# Linux x86_64 only (the build box and GitHub's ubuntu runners). On a Mac, use a newer uv or pyenv.
set -euo pipefail

RELEASE=20261110
FILE=cpython-3.12.16+${RELEASE}-x86_64-unknown-linux-gnu-install_only_stripped.tar.gz
SHA256=6a9e62dad033790aef722dbd370e0ce76ce17b73627ba3ae679f537049350b39
DEST="${UV_PYTHON_INSTALL_DIR:-$HOME/.local/share/uv/python}/cpython-3.12.16-linux-x86_64-gnu"

if [ -x "$DEST/bin/python3.12" ] && "$DEST/bin/python3.12" --version | grep -q "3.12.16"; then
  echo "CPython 3.12.16 already installed at $DEST"
  exit 0
fi
[ "$(uname -s)-$(uname -m)" = "Linux-x86_64" ] || { echo "only Linux x86_64 is supported by this script" >&2; exit 1; }

# The tarball is kept in a cache directory (no cleanup step), so a rerun does not download it again.
CACHE="${XDG_CACHE_HOME:-$HOME/.cache}/experiment-analyzer"
mkdir -p "$CACHE"
if ! echo "${SHA256}  $CACHE/$FILE" | sha256sum -c --status - 2>/dev/null; then
  curl -fsSL -o "$CACHE/$FILE" "https://github.com/astral-sh/python-build-standalone/releases/download/${RELEASE}/${FILE}"
fi
echo "${SHA256}  $CACHE/$FILE" | sha256sum -c -
mkdir -p "$DEST"
tar -xzf "$CACHE/$FILE" -C "$DEST" --strip-components=1
"$DEST/bin/python3.12" --version
