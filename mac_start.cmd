#!/bin/sh
set -eu

# Resolve relative paths from the launcher, including paths with spaces.
case "$0" in
  */*) launcher_dir=${0%/*} ;;
  *) launcher_dir=. ;;
esac
case "$launcher_dir" in
  /*) cd "$launcher_dir" ;;
  *) cd "./$launcher_dir" ;;
esac

if ! command -v node >/dev/null 2>&1; then
  printf '%s\n' 'Node.js is required. Install Node.js and open a new terminal.' >&2
  exit 1
fi

exec node ./scripts/dev-all.mjs "$@"
