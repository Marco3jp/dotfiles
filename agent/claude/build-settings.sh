#!/bin/sh
# agent/claude/settings.json に ~/.claude/settings.*.json を重ねて ~/.claude/settings.json を書き出す
set -eu

base="$(cd "$(dirname "$0")" && pwd)/settings.json"
out="$HOME/.claude/settings.json"

usage() {
  echo "usage: $0 --dry-run | --write" >&2
  echo "  --dry-run  今の $out との差分だけを出す" >&2
  echo "  --write    差分を出してから $out を書き換える（元は $out.prev に残す）" >&2
  exit 2
}

[ $# -eq 1 ] || usage
case "$1" in
  --dry-run|--write) mode="$1" ;;
  *) usage ;;
esac

set -- "$base"
for f in "$HOME"/.claude/settings.*.json; do
  [ -f "$f" ] && set -- "$@" "$f"
done

tmp="$(mktemp)"
trap 'rm -f "$tmp"' EXIT
jq -s 'reduce .[] as $x ({}; . * $x)' "$@" > "$tmp"

echo "重ねたファイル: $*" >&2
if [ -f "$out" ] && diff -u "$out" "$tmp"; then
  echo "差分なし" >&2
  exit 0
fi

if [ "$mode" = --write ]; then
  [ -f "$out" ] && cp "$out" "$out.prev"
  cp "$tmp" "$out"
  echo "書き出し: $out" >&2
fi
