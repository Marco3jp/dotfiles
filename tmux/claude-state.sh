#!/bin/sh
# Claude Code の状態を tmux ペインの @claude_state に書き込む（hooks から呼ばれる）
[ -n "$TMUX_PANE" ] || exit 0
p="$TMUX_PANE"
get() { tmux show -pqv -t "$p" "$1"; }
put() { tmux set -p -t "$p" "$1" "$2"; }

if [ -n "$1" ]; then
  put @claude_state "$1"
  exit 0
fi

eval "$(jq -r '@sh "ev=\(.hook_event_name // "") tool=\(.tool_name // "") agent=\(.agent_id // "") bg=\(.tool_input.run_in_background // false) nt=\(.notification_type // "") fin=\([(.prompt // "") | scan("<status>[a-z_]+</status>")] | length)"')"

state=$(get @claude_state)
base=$(get @claude_base)
bgn=$(get @claude_bg)
case "$bgn" in ''|*[!0-9]*) bgn=0 ;; esac

case "$ev" in
  SessionStart)
    bgn=0; base=idle; state=idle ;;
  SessionEnd)
    tmux set -pu -t "$p" @claude_state
    tmux set -pu -t "$p" @claude_base
    tmux set -pu -t "$p" @claude_bg
    exit 0 ;;
  UserPromptSubmit)
    bgn=$((bgn - fin)); [ "$bgn" -lt 0 ] && bgn=0
    base=busy; state=busy ;;
  PreToolUse)
    [ -z "$agent" ] && { base=busy; state=busy; } ;;
  PermissionRequest|Elicitation)
    state=ask ;;
  Notification)
    case "$nt" in
      elicitation_dialog|elicitation_url_dialog|agent_needs_input) state=ask ;;
    esac ;;
  PostToolUse|PostToolUseFailure|PermissionDenied|ElicitationResult)
    if [ -z "$agent" ]; then
      if [ "$ev" = PostToolUse ] && { [ "$bg" = true ] || [ "$tool" = Monitor ]; }; then
        bgn=$((bgn + 1))
      fi
      base=busy; state=busy
    elif [ "$state" = ask ]; then
      state=${base:-busy}
    fi ;;
  Stop)
    if [ "$bgn" -gt 0 ]; then base=monitor; else base=done; fi
    state=$base ;;
  StopFailure)
    base=done; state=done ;;
  *)
    exit 0 ;;
esac

put @claude_bg "$bgn"
put @claude_base "$base"
put @claude_state "$state"
