#!/bin/sh
# dotfiles をシンボリックリンクで配置する。既にあるファイルは ~/.dotfiles-backup/<日時>/ に移してから張る
set -eu

usage() {
  echo "usage: $0 --dry-run | --run" >&2
  echo "  --dry-run  張るリンクと移すファイルを出すだけで、何も変えない" >&2
  echo "  --run      リンクを張り、~/.claude/settings.json を build-settings.sh --write で書き出す" >&2
  exit 2
}

[ $# -eq 1 ] || usage
case "$1" in
  --dry-run|--run) mode="$1" ;;
  *) usage ;;
esac

root="$(cd "$(dirname "$0")" && pwd)"
backup="$HOME/.dotfiles-backup/$(date +%Y%m%d-%H%M%S)"

# link リポジトリ内のパス 置き先
link() {
  src="$root/$1"
  dst="$2"
  if [ -L "$dst" ] && [ "$(readlink "$dst")" = "$src" ]; then
    echo "済み: $dst"
    return 0
  fi
  if [ -e "$dst" ] || [ -L "$dst" ]; then
    echo "退避: $dst -> $backup/${dst#"$HOME"/}"
    if [ "$mode" = --run ]; then
      mkdir -p "$backup/$(dirname "${dst#"$HOME"/}")"
      mv "$dst" "$backup/${dst#"$HOME"/}"
    fi
  fi
  echo "リンク: $dst -> $src"
  if [ "$mode" = --run ]; then
    mkdir -p "$(dirname "$dst")"
    ln -s "$src" "$dst"
  fi
}

skip() {
  echo "スキップ: $1"
}

# tmux / byobu
link tmux/.tmux.conf "$HOME/.tmux.conf"
link tmux/mem.sh "$HOME/.config/tmux/mem.sh"
link tmux/claude-state.sh "$HOME/.config/tmux/claude-state.sh"
link tmux/ticker.py "$HOME/.config/tmux/ticker.py"
link byobu/.tmux.conf "$HOME/.config/byobu/.tmux.conf"

# Claude Code（settings.json はリンクにせず build-settings.sh で書き出す）
c=agent/claude
link $c/CLAUDE.md "$HOME/.claude/CLAUDE.md"
link $c/rules "$HOME/.claude/rules"
link $c/themes/darcula.json "$HOME/.claude/themes/darcula.json"
link $c/statusline-command.sh "$HOME/.claude/statusline-command.sh"
link $c/hooks/ja_style_hook.py "$HOME/.claude/hooks/ja_style_hook.py"
link $c/agents/review-qa-page.md "$HOME/.claude/agents/review-qa-page.md"
link $c/agents/review-qa-page "$HOME/.claude/agents/review-qa-page"
for s in prompt-interview repo-page issue-refinement; do
  link $c/skills/$s "$HOME/.claude/skills/$s"
done
if [ "$mode" = --run ]; then
  mkdir -p "$HOME/.claude"
  "$root/$c/build-settings.sh" --write
else
  "$root/$c/build-settings.sh" --dry-run
fi

# Linux で使っているもの（fish・xfce4・fcitx5）
if [ "$(uname)" = Linux ]; then
  link fish/functions/fish_prompt.fish "$HOME/.config/fish/functions/fish_prompt.fish"
  link fish/functions/fish_right_prompt.fish "$HOME/.config/fish/functions/fish_right_prompt.fish"
  link terminal/terminalrc "$HOME/.config/xfce4/terminal/terminalrc"
  link im-module/.xprofile "$HOME/.xprofile"
  if command -v fcitx5 >/dev/null; then
    link im-module/fcitx5/classicui.conf "$HOME/.config/fcitx5/conf/classicui.conf"
    link im-module/fcitx5/profile "$HOME/.config/fcitx5/profile"
    link im-module/fcitx5/dark.conf "$HOME/.local/share/fcitx5/themes/dark/theme.conf"
  else
    skip "fcitx5 の設定（fcitx5 が入っていない）"
  fi
fi

# JetBrains: いちばん新しい IntelliJIdea の設定ディレクトリに置く
case "$(uname)" in
  Darwin) jb="$HOME/Library/Application Support/JetBrains" ;;
  *) jb="$HOME/.config/JetBrains" ;;
esac
idea="$(ls -d "$jb"/IntelliJIdea* 2>/dev/null | sort -V | tail -n 1)"
if [ -n "$idea" ]; then
  link jetbrains/IntelliJIdea/fileTemplates "$idea/fileTemplates"
else
  skip "JetBrains の fileTemplates（IntelliJIdea の設定ディレクトリが無い）"
fi
