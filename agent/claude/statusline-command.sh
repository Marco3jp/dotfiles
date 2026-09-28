#!/bin/sh
input=$(cat)

model=$(echo "$input" | jq -r '.model.display_name // .model.id // "unknown"')

five_pct=$(echo "$input" | jq -r '.rate_limits.five_hour.used_percentage // empty')
five_reset=$(echo "$input" | jq -r '.rate_limits.five_hour.resets_at // empty')
if [ -n "$five_pct" ]; then
  five_str="5h:$(printf '%.0f' "$five_pct")%"
  if [ -n "$five_reset" ]; then
    five_reset_time=$(date -r "$five_reset" "+%H:%M" 2>/dev/null)
    now=$(date +%s)
    diff=$(( five_reset - now ))
    if [ "$diff" -gt 0 ]; then
      diff_h=$(( diff / 3600 ))
      diff_m=$(( (diff % 3600) / 60 ))
      five_str="${five_str}(${five_reset_time} -${diff_h}h${diff_m}m)"
    else
      five_str="${five_str}(${five_reset_time})"
    fi
  fi
else
  five_str="5h:--"
fi

week_pct=$(echo "$input" | jq -r '.rate_limits.seven_day.used_percentage // empty')
if [ -n "$week_pct" ]; then
  week_str="7d:$(printf '%.0f' "$week_pct")%"
else
  week_str="7d:--"
fi

cwd=$(echo "$input" | jq -r '.worktree.original_cwd // .workspace.project_dir // .cwd // empty')
branch=""
if [ -n "$cwd" ]; then
  branch=$(git -C "$cwd" --no-optional-locks symbolic-ref --short HEAD 2>/dev/null)
fi
[ -z "$branch" ] && branch="--"

printf '%s  %s  %s  %s  %s' "$model" "$five_str" "$week_str" "$branch" "$cwd"
