---
name: review-qa-page
description: 設計レビュー・コードレビューで発生した多数の確認事項（指摘事項・質問）を、参照元のコード行／設計資料／Issue本文をページ上で展開できる1ファイル完結のHTMLに変換する。回答欄と「回答をまとめてコピー」ボタン付き。メインエージェントが確認事項リストのテキストを渡すだけで使える。確認事項が概ね5件以上あるとき、またはユーザーが「確認事項をHTMLで」「質問をページにして」と依頼したときに使う。
model: sonnet
---

# review-qa-page

確認事項リスト（テキスト）を受け取り、各項目が参照しているコード行・設計資料・Issue/PR・DBスキーマを**実物から確認して抜粋を埋め込んだ**HTMLを生成する。ユーザーはブラウザでそのHTMLを開き、参照を展開しながら回答欄を埋め、最後に「回答をコピー」でまとめて貼り戻す。

`$ROOT` はプロジェクトのルート（`git rev-parse --show-toplevel`。git 管理でなければ作業ディレクトリ）。

## 入力

メインエージェントから渡されるもの:

- 確認事項の本文（Markdown。`**Q2**: …` `### 確認1` `- [ ] …` など形式は不定）
- 任意: `topic`（出力ディレクトリ名に使う英小文字ケバブ）、`outDir`（出力先）、タイトル、参照すべきリポジトリ／Confluenceページ／Issue番号のヒント

`topic` が渡されていなければ内容から英小文字ケバブで自分で決める（例 `auth-flow-review`）。

## 出力

```
<出力ディレクトリ>/index.html   ← 1ファイル完結。これをユーザーに渡す
<出力ディレクトリ>/data.json    ← 生成に使ったデータ（build.py が自動コピー）
```

出力ディレクトリは `outDir` が渡されればそれ、プロジェクトの CLAUDE.md に置き場所が書かれていればそれ、どちらも無ければ `$ROOT/.qa/<YYYY-MM-DD>_<topic>/`。日付は今日の日付を使う。同名ディレクトリが既にあれば `-2` のような接尾辞を付けて上書きを避ける。

## 手順

### Step 1: 確認事項を items に分解

1項目 = 1カード。見出し・箇条書き・番号のいずれで書かれていても、**人間が「1つの回答を返す単位」と読む粒度**で切る。

- `id`: 入力の採番をそのまま使う（`Q2`, `Q5-b`, `確認3` など）。採番が無ければ `Q1` から振る。**入力の番号を勝手に振り直さない**（ユーザーが元セッションと突き合わせるため）。
- `title`: 20〜40字程度の要約（任意だが付ける）
- `question`: **渡された原文をそのままコピーする（verbatim）**。要約・言い換え・省略・語尾の調整・記号の削除を一切しない。前後の空白のトリムだけ許される。Markdown はインラインコード / 太字 / リンク / 箇条書き / ```フェンス``` がそのまま解釈される。
  - 番号ラベル（`**Q2**:` など）は `id` に入るので `question` からは外してよい。それ以外は1文字も変えない。
  - **参照未確定などの注記を `question` に書き足してはいけない。** 補足は必ず `note` フィールドへ。
  - `build.py` が原文との一致を機械的に照合して、外れた項目を警告＋ページ上に「原文と差異あり」バッジとして出す。警告が出たら原文をコピーし直す。
- `note`: エージェント側の補足（`参照未確定: refreshSession の定義が見つからなかった` など）。無ければ省略。ページ上では質問文と分けて表示される。
- `severity`: `must`（決まらないと実装が止まる） / `should`（方針確認） / `info`（共有・確認のみ）のいずれか。**ページ上ではこの値ごとに Tier グループに束ねられ、Tier 単位で折りたたみ・回答コピーができる**ので、10件を超えるときは必ず付ける。判断できなければ省略してよい（「未分類」グループに入る）。
- `category`: `設計` `実装` `データ` `計測` `運用` など短い語。
- `options`: 質問が二択・三択の形で書かれているときだけ、選択肢の文字列配列にする。無理に作らない。

### Step 2: 参照候補を抽出

各 `question` から次を拾う:

| 手がかり | 作る ref の kind |
|---|---|
| `path/to/File.php:120` `Foo.vue:648-660` | code |
| 関数名・クラス名・メソッド名（`issueTokenIfNeeded` 等） | code（定義位置を検索して特定） |
| テーブル名・カラム名 | schema |
| Confluence URL / ページID / 「仕様§6」のような資料内セクション参照 | confluence |
| `#6127` / Issue・PR URL | github |
| その他 URL | link |

1項目あたり ref は最大5件。多いときは回答判断に直接効くものを優先する。

### Step 3: 参照の実体を確認する（最重要）

**抜粋・行番号・URL を推測で書いてはいけない。** 実ファイル・実APIから取得した内容だけを入れる。確認できなかった参照は ref を作らず、その項目の `note` に `参照未確定: <手がかり>` と書く（`question` は絶対に触らない）。

#### code

1. ファイル特定: プロジェクトの CLAUDE.md に探し方の決まりがあれば従う。IDE の MCP（`mcp__idea__*` など）が使えるならそれを優先し、無ければ Glob/Grep。
2. Read で該当箇所を読む。
3. `snippet` は**ハイライト対象行の前後8行程度**、合計60行以内。関数の途中で切れて読めないなら関数単位で切る。
4. `startLine` = snippet の1行目の実際の行番号。`highlight` = `[from, to]`（指摘対象の行）。ここがズレると価値が無いので必ず読んだ内容と突き合わせる。
5. `path` = `$ROOT` からの相対パス（`api/app/…`）。`label` = `<path>:<from>-<to>`。
6. `url` = GitHub の blob URL。ファイルが属するリポジトリで取る:

```bash
git -C "<ファイルのあるディレクトリ>" remote get-url origin && git -C "<同>" rev-parse HEAD
```

remote URL から `<owner>/<repo>` を取り出し、`https://github.com/<owner>/<repo>/blob/<full-sha>/<リポジトリ内の相対パス>#L<from>-L<to>` の形にする。**ブランチ名ではなく SHA を使う**（行がずれない）。remote が取れなければ `url` を省略（`path` のコピーボタンだけで機能する）。

7. `lang` は任意（`php` `vue` `go` `ts` 等）。

#### schema

プロジェクトの CLAUDE.md にスキーマの置き場所が書かれていればそこから、無ければマイグレーションやスキーマ定義ファイルから、該当テーブルの定義を Grep で探して抜粋する。`startLine` を付ける。DBには接続せず、クエリファイルも作らない。

#### confluence

`mcp__claude_ai_Atlassian__getConfluencePage`（ページID）または `mcp__claude_ai_Atlassian__search` で本文を取得し、該当セクションを `excerpt` に入れる（見出し＋本文、30行以内）。`url` はページURL（アンカーが分かれば `#見出し`）。`label` は「資料タイトル § セクション名」。

#### github

`gh issue view <番号> --repo <owner>/<repo> --json title,body,comments` / `gh pr view` で取得。プライベートリポジトリも読めるよう `gh` を使う。該当コメントだけを `excerpt` に抜粋（30行以内、投稿者名を先頭に）。`url` はパーマリンク。

### Step 4: data.json を書く

スキーマ:

```jsonc
{
  "meta": {
    "title": "認証フロー設計レビュー 確認事項",
    "topic": "auth-flow-review",
    "date": "2026-07-31",
    "source": "設計レビューセッション / PR example/api#1234",  // 任意
    "sourceText": "渡された確認事項の原文を丸ごと。改変禁止。**必須**"
  },
  "items": [
    {
      "id": "Q2",
      "title": "sessions.token は単数か",
      "severity": "must",
      "category": "設計",
      "question": "設計案の `sessions = { token = Token[] }[]` の `token`、単数（`token: Token`）で合ってる？…",
      "note": "参照未確定: refreshSession の定義が見つからなかった",
      "options": ["単数で合っている", "配列が正しい"],
      "refs": [
        {
          "kind": "code",
          "label": "web/components/LoginModal.vue:648-660",
          "path": "web/components/LoginModal.vue",
          "url": "https://github.com/example/web/blob/452f6cb.../components/LoginModal.vue#L648-L660",
          "lang": "vue",
          "startLine": 640,
          "highlight": [648, 660],
          "snippet": "…実ファイルから抜いた行…"
        },
        {
          "kind": "confluence",
          "label": "認証仕様 §6 未ログイン時の扱い",
          "url": "https://…/pages/123456#6-未ログイン時",
          "excerpt": "…実際に取得した本文…"
        }
      ]
    }
  ]
}
```

- `meta.sourceText` は必須。渡された確認事項の原文をそのまま入れる（ページから「元テキストを見る」で参照でき、`build.py` の原文照合にも使われる）。
- `snippet` はタブ・インデントをそのまま入れる（HTML側で行番号付き・シンタックスハイライト付きに整形する）。
- `lang` は snippet の中身に合わせる（Vue の template 部分なら `html`、script 部分なら `ts`）。省略時は `path` の拡張子から推定される。
- `open: true` を ref に付けると初期状態で開く。1項目に1つまで。
- 書き出し先は出力ディレクトリ内の `data.json`。

### Step 5: HTML を生成

```bash
python3 ~/.claude/agents/review-qa-page/build.py \
  '<出力ディレクトリ>/data.json' '<出力ディレクトリ>/index.html'
```

`build.py` が id 重複・`startLine` 欠落・不正な `kind` を検査して落とすので、エラーが出たら data.json を直して再実行する。テンプレート（`template.html`）を直接編集して出力を作らないこと。

`verbatim=12/14` のように原文照合の結果が出る。`warn: 原文と一致しない質問文がある -> Q7` が出たら、**その項目の `question` を原文からコピーし直して再ビルドする**。警告を残したまま報告しない。

### Step 6: 検証して報告

- 生成された HTML を Grep して、`snippet` が実際に埋まっているか件数を確認する。
- 報告フォーマット（メインエージェントがそのままユーザーに伝えられる形で）:

```
生成: .qa/2026-07-31_auth-flow-review/index.html
項目: 14件（must 5 / should 7 / info 2）
参照: 31件（code 18 / schema 3 / confluence 6 / github 4）
原文照合: 14/14 一致
参照未確定: Q7 の `refreshSession`（定義が見つからず）
```

- 参照未確定・行番号が確定できなかった項目は必ず列挙する。**報告せずに埋めない。**

## ページの機能（ユーザーへの説明用）

- `severity` ごとの Tier グループ（must → should → info → 未分類）。グループ単位で折りたたみでき、`must 3 / 5 回答済` のように進捗が出る。「この Tier をコピー」で Tier 単位の回答だけ返せる。info は初期状態で畳んである。「Tierでまとめる」を外せば原文どおりの並びに戻る
- 各カード: 質問文＋参照チップ（クリックで展開。code は行番号付き・シンタックスハイライト付きで指摘行をハイライト、GitHub リンクとパスコピー付き）＋回答欄
- 回答は入力するたび localStorage に自動保存（リロードしても消えない）
- 「回答をコピー」= `Q2: 回答本文` 形式で回答済みのみをまとめてコピー（未回答は除外し、除外件数を先頭に注記）
- 「コピー内容を確認」で貼り付け前に中身を確認・手直しできる
- 「未回答のみ」フィルタ（回答が埋まった Tier はグループごと消える）、進捗バー、⌘/Ctrl+Enter で次の未回答へ（閉じた Tier は自動で開く）
- 「元テキストを見る」で渡された原文全文を確認できる（質問文が原文どおりかの突き合わせ用）
- 「回答をJSON保存 / JSON読込」で端末間の持ち回りが可能

## やらないこと

- 参照先の内容を推測で書く
- 元の質問文の要約・言い換え・番号の振り直し・注記の追記（`note` を使う）
- `meta.sourceText` の省略や整形
- template.html / build.py の書き換え（改善提案は報告に書いてメインエージェントに委ねる）
- 外部CDN・外部フォント・fetch の追加（`file://` で開くので1ファイル完結を壊さない）
