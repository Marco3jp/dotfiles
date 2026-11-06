# NOTE

dotfiles を各環境に配置する手順。

リポジトリは `~/dev/dotfiles` に置く。agent/claude/CLAUDE.md が rules を `@~/dev/dotfiles/agent/claude/rules/...` で読むため。

## 必要なもの

- jq: claude-state.sh・statusline-command.sh・build-settings.sh が使う
- python3: ticker.py と日本語の書き方 hook が使う
- tmux 3.3 以上: .tmux.conf で allow-passthrough と terminal-features を使う
- notify-send（Linux のみ）: Claude Code の通知を出す。macOS は osascript で出す

## 配置する

最初にこれを実行して、`$DOTFILES` を決め、リンク先のディレクトリを作る。

```sh
DOTFILES=~/dev/dotfiles
mkdir -p ~/.config/tmux ~/.config/byobu ~/.claude/themes ~/.claude/hooks ~/.claude/agents ~/.claude/skills
```

リンク先に同じ名前のファイルがあると `ln -s` は失敗する。そのファイルの中身を見て、残したい値があれば「機械ごとに置くもの」へ移してから消す。

### tmux（macOS・Linux）

```sh
ln -s $DOTFILES/tmux/.tmux.conf ~/
ln -s $DOTFILES/tmux/mem.sh ~/.config/tmux/
ln -s $DOTFILES/tmux/claude-state.sh ~/.config/tmux/
ln -s $DOTFILES/tmux/ticker.py ~/.config/tmux/
ln -s $DOTFILES/byobu/.tmux.conf ~/.config/byobu/
```

- mem.sh: ステータスバーにメモリ使用率を出す。macOS は vm_stat、Linux は free から計算する
- claude-state.sh: Claude Code の hooks から呼ばれ、tmux のタブに作業中・入力待ちの色を付ける
- ticker.py: ステータス3・4行目に NHK ニュースと気象庁の予報を流す
  - 地域・ニュースのカテゴリ・速さは ~/.config/tmux/local.conf に `set-environment -g TICKER_JMA_OFFICE 270000` のように書いて変える（値は ticker.py 冒頭）
- byobu/.tmux.conf: byobu は ~/.tmux.conf を読まないので、これで source させる

### Claude Code（macOS・Linux）

```sh
ln -s $DOTFILES/agent/claude/CLAUDE.md ~/.claude/
ln -s $DOTFILES/agent/claude/themes/darcula.json ~/.claude/themes/
ln -s $DOTFILES/agent/claude/statusline-command.sh ~/.claude/
ln -s $DOTFILES/agent/claude/hooks/ja_style_hook.py ~/.claude/hooks/
ln -s $DOTFILES/agent/claude/agents/review-qa-page.md ~/.claude/agents/
ln -s $DOTFILES/agent/claude/agents/review-qa-page ~/.claude/agents/
ln -s $DOTFILES/agent/claude/skills/prompt-interview ~/.claude/skills/
ln -s $DOTFILES/agent/claude/skills/repo-page ~/.claude/skills/
ln -s $DOTFILES/agent/claude/skills/issue-refinement ~/.claude/skills/
$DOTFILES/agent/claude/build-settings.sh --dry-run
$DOTFILES/agent/claude/build-settings.sh --write
```

- ~/.claude/settings.json はリンクにせず、build-settings.sh で書き出す。agent/claude/settings.json に ~/.claude/settings.*.json を重ねて作る。autoMode はユーザー設定からしか読まれないので、機械ごとの値を足せるようにしている
  - 重ねるとき、オブジェクトは中身ごとにまとめ、配列（hooks の各イベント・permissions.deny など）は後ろに足す
  - /config などで変えた値は次の書き出しで消える。残したい値は agent/claude/settings.json か settings.*.json に書く
  - agent/claude/settings.json が変わったら（git pull の後など）--dry-run で差分を見てから --write し直す
  - 前に ~/.claude/settings.json をリンクで置いていた機械では、--write がリンクを外してファイルに置き換える
- 日本語の書き方 hook に、あるプロジェクトだけで足したい語は、そのプロジェクトの .claude/ja-style-words.json に書く

### Linux で使っているもの（fish・xfce4・fcitx5）

```sh
mkdir -p ~/.config/fish/functions ~/.config/xfce4/terminal ~/.config/fcitx5/conf ~/.local/share/fcitx5/themes/dark
ln -s $DOTFILES/fish/functions/fish_prompt.fish ~/.config/fish/functions/
ln -s $DOTFILES/fish/functions/fish_right_prompt.fish ~/.config/fish/functions/
ln -s $DOTFILES/terminal/terminalrc ~/.config/xfce4/terminal/
ln -s $DOTFILES/im-module/.xprofile ~/
ln -s $DOTFILES/im-module/fcitx5/classicui.conf ~/.config/fcitx5/conf/
ln -s $DOTFILES/im-module/fcitx5/profile ~/.config/fcitx5/
ln -s $DOTFILES/im-module/fcitx5/dark.conf ~/.local/share/fcitx5/themes/dark/theme.conf
```

- dark.conf はこのリンク先で読まれるか確かめていない。手元では ~/.local/share/fcitx5/themes/default/theme.conf に置いていた

### JetBrains IDE

```sh
ln -s $DOTFILES/jetbrains/IntelliJIdea/fileTemplates/ <IDE の設定ディレクトリ>/
```

- IDE の設定ディレクトリは、Linux なら ~/.config/JetBrains/IntelliJIdea<バージョン>、macOS なら ~/Library/Application\ Support/JetBrains/IntelliJIdea<バージョン>。入っているバージョンに合わせる

### Mozc

- im-module/mozc/keymap.txt: Mozc のキー設定の編集画面からインポートする
- im-module/mozc/dictionary/otaku.txt: Mozc の辞書ツールで、新しいユーザー辞書としてインポートする
- im-module/mozc/candidate_priority.tsv: 手を入れた Mozc が読む、読みごとの候補の順位。macOS では次のようにコピーする。リンクで読めるかは確かめていないのでコピーにしている

```sh
cp $DOTFILES/im-module/mozc/candidate_priority.tsv ~/Library/Application\ Support/Mozc/
```

## 機械ごとに置くもの

次のファイルはリポジトリに入れず、機械ごとに書く。仕事で使う設定や、その機械にしか無いものを指す設定はここに書く（リポジトリに入れないものは CLAUDE.md を参照）。

- ~/.claude/settings.*.json: その機械だけの Claude Code の設定。build-settings.sh が agent/claude/settings.json に重ねる。用途ごとに分けてよい（settings.work.json など）
- ~/.config/tmux/local.conf: .tmux.conf の最後に source-file する。status-format などを上書きできる。無ければ読まない

## 例外

- Mozc の設定（config1.db など）はバイナリなので管理していない

## 整理できていないもの

- IdeaのColor
  - 配色ファイル（Marco_sDarcula.icls）はリポジトリに入れていない
  - 秘伝のソースになっていて中身が適切か判断しきれない
- IdeaのKeymap
  - 実はあんまりちゃんと決めてこなかった
  - 決めるところから
- IdeaのOptions
  - 多すぎて中身の精査がしんどい
  - がんばって
- xfce4の色々
  - panel
  - appfinder
    - 主にショートカット
  - keyboard shortcuts
  - screensaver
  - wm
