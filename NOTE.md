# NOTE

## シンボリックリンクのリスト

- ln -s $DOTFILES_ROOT_PWD/fish/functions/fish_prompt.fish ~/.config/fish/function/
- ln -s $DOTFILES_ROOT_PWD/fish/functions/fish_right_prompt.fish ~/.config/fish/function/
- ln -s $DOTFILES_ROOT_PWD/terminal/terminalrc ~/.config/xfce4/terminal/
- ln -s $DOTFILES_ROOT_PWD/im-module/.xprofile ~/
- ln -s $DOTFILES_ROOT_PWD/fcitx5/classicui.conf ~/.config/fcitx5/conf/
- ln -s $DOTFILES_ROOT_PWD/fcitx5/profile ~/.config/fcitx5/
- ln -s $DOTFILES_ROOT_PWD/fcitx5/dark.conf ~/.local/share/fcitx5/themes/dark/theme.conf
  - これで動くのか不明（手元では ~/.local/share/fcitx5/themes/default/theme.conf なので）
- ln -s $DOTFILES_ROOT_PWD/jetbrains/IntelliJIdea/fileTemplates/ ~/.config/JetBrains/IntelliJIdea2021.3/

## 例外

- mozcの設定はsqliteっぽいバイナリなので一旦保留（バイナリをバージョン管理すれば対処できそう？）

## 整理できていないもの
- IdeaのColor
  - ln -s $DOTFILES_ROOT_PWD/jetbrains/IntelliJIdea/colors/Marco_sDarcula.icls ~/.config/JetBrains/IntelliJIdea2021.3/colors/
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
