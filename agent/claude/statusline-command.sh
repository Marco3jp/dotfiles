#!/bin/sh
# Claude Code のステータスライン（ステータスライン工房で作成）
input=$(cat)
out=""
SEP=' │ '

# seg コード 文字列 [1=前とつなげる]
seg() {
  [ -z "$2" ] && return 0
  [ -n "$out" ] && [ "$3" != 1 ] && out="$out$SEP"
  if [ -n "$1" ]; then
    out="$out$(printf '\033[%sm' "$1")$2$(printf '\033[0m')"
  else
    out="$out$2"
  fi
}

# モデル
v=""
v=$(printf '%s' "$input" | jq -r '.model.display_name // .model.id // empty')
seg '' "$v"

# effort
v=""
v=$(printf '%s' "$input" | jq -r '.effort.level // empty')
[ -n "$v" ] && v='('"$v"')'
seg '' "$v" 1

# 使用量
v=""
p=$(printf '%s' "$input" | jq -r '.rate_limits.five_hour.used_percentage // empty')
[ -n "$p" ] && v=$(printf '%.0f%%' "$p")
[ -z "$v" ] && v='--'
[ -n "$v" ] && v='5h:'"$v"
hp=""
hp=$(printf '%s' "$input" | jq -r '(.rate_limits.five_hour.used_percentage // empty) | floor' 2>/dev/null)
c=''
if [ -n "$hp" ]; then
  if [ "$hp" -ge 80 ]; then col=31; elif [ "$hp" -ge 50 ]; then col=33; else col=32; fi
  c="${c:+$c;}$col"
fi
seg "$c" "$v"

# リセットまで
v=""
r=$(printf '%s' "$input" | jq -r '(.rate_limits.five_hour.resets_at // empty) | floor' 2>/dev/null)
if [ -n "$r" ]; then
  t=$(date -d "@$r" '+%H:%M' 2>/dev/null || date -r "$r" '+%H:%M' 2>/dev/null)
  left=$(( r - $(date +%s) ))
  if [ "$left" -ge 86400 ]; then rem="$((left / 86400))d$((left % 86400 / 3600))h"; else rem="$((left / 3600))h$((left % 3600 / 60))m"; fi
  if [ "$left" -gt 0 ]; then v="$t -$rem"; else v="$t"; fi
fi
[ -n "$v" ] && v='('"$v"')'
seg '' "$v" 1

# 使用量
v=""
p=$(printf '%s' "$input" | jq -r '.rate_limits.seven_day.used_percentage // empty')
[ -n "$p" ] && v=$(printf '%.0f%%' "$p")
[ -z "$v" ] && v='--'
[ -n "$v" ] && v=' 7d:'"$v"
hp=""
hp=$(printf '%s' "$input" | jq -r '(.rate_limits.seven_day.used_percentage // empty) | floor' 2>/dev/null)
c=''
if [ -n "$hp" ]; then
  if [ "$hp" -ge 80 ]; then col=31; elif [ "$hp" -ge 50 ]; then col=33; else col=32; fi
  c="${c:+$c;}$col"
fi
seg "$c" "$v" 1

# コンテキスト
v=""
v=$(printf '%s' "$input" | jq -r 'def k: if . >= 1000000 then "\((. / 100000 | floor) / 10)M" elif . >= 1000 then "\((. / 100 | floor) / 10)k" else tostring end; .context_window | if . == null or .total_input_tokens == null then empty else "\(.total_input_tokens | k)/\(.context_window_size // 200000 | k)" end')
[ -z "$v" ] && v='--'
hp=""
hp=$(printf '%s' "$input" | jq -r '(.context_window.used_percentage // empty) | floor' 2>/dev/null)
c=''
if [ -n "$hp" ]; then
  if [ "$hp" -ge 80 ]; then col=31; elif [ "$hp" -ge 50 ]; then col=33; else col=32; fi
  c="${c:+$c;}$col"
fi
seg "$c" "$v"

# コンテキスト
v=""
p=$(printf '%s' "$input" | jq -r '(.context_window.used_percentage // empty) | floor' 2>/dev/null)
if [ -n "$p" ]; then
  n=$(( (p + 5) / 10 )); [ "$n" -gt 10 ] && n=10
  i=0
  while [ "$i" -lt 10 ]; do
    if [ "$i" -lt "$n" ]; then v="$v█"; else v="$v░"; fi
    i=$((i + 1))
  done
  v="$v $p%"
fi
[ -n "$v" ] && v=' '"$v"
hp=""
hp=$(printf '%s' "$input" | jq -r '(.context_window.used_percentage // empty) | floor' 2>/dev/null)
c=''
if [ -n "$hp" ]; then
  if [ "$hp" -ge 80 ]; then col=31; elif [ "$hp" -ge 50 ]; then col=33; else col=32; fi
  c="${c:+$c;}$col"
fi
seg "$c" "$v" 1

# プロンプトキャッシュ
v=""
v=$(printf '%s' "$input" | jq -r '.prompt_cache.hit_ratio | if . == null then empty else "\(. * 100 | floor)%" end')
[ -z "$v" ] && v='--'
[ -n "$v" ] && v=' cache '"$v"
seg '' "$v" 1

# 増減した行
v=""
v=$(printf '%s' "$input" | jq -r 'if .cost.total_lines_added == null then empty else "+\(.cost.total_lines_added) -\(.cost.total_lines_removed // 0)" end')
[ -z "$v" ] && v='--'
seg '' "$v"

# ディレクトリ
v=""
v=$(printf '%s' "$input" | jq -r '.worktree.original_cwd // .workspace.project_dir // .cwd // empty')
v=$(printf '%s' "$v" | sed "s|^$HOME|~|")
[ -z "$v" ] && v='--'
seg '2' "$v"

# 経過時間
v=""
ms=$(printf '%s' "$input" | jq -r '(.cost.total_duration_ms // empty) | floor' 2>/dev/null)
if [ -n "$ms" ]; then
  s=$((ms / 1000))
  if [ "$s" -ge 3600 ]; then v="$((s / 3600))h$((s % 3600 / 60))m"; else v="$((s / 60))m$((s % 60))s"; fi
fi
[ -n "$v" ] && v='total '"$v"
seg '2' "$v"

# 経過時間
v=""
ms=$(printf '%s' "$input" | jq -r '(.cost.total_api_duration_ms // empty) | floor' 2>/dev/null)
if [ -n "$ms" ]; then
  s=$((ms / 1000))
  if [ "$s" -ge 3600 ]; then v="$((s / 3600))h$((s % 3600 / 60))m"; else v="$((s / 60))m$((s % 60))s"; fi
fi
[ -n "$v" ] && v=' wait '"$v"
seg '2' "$v" 1

printf '%s' "$out"
