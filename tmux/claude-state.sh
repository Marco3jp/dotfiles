#!/bin/sh
# Claude Code の状態を tmux ペインの @claude_state に書き込む（hooks から呼ばれる）
[ -n "$TMUX_PANE" ] || exit 0
tmux set -p -t "$TMUX_PANE" @claude_state "$1"
