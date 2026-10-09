#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""「日本語の書き方」のルール(rules/japanese-writing.md)を機械チェックする hook.

  Stop        : 直前の assistant 返答をチェック
  PreToolUse  : Bash(gh pr/issue の本文), Write/Edit/NotebookEdit の書き込み内容をチェック

exit 2 + stderr で差し戻す。
HARD は常に差し戻し。SOFT は同じ内容で再実行されたら通す(誤検出の逃げ道)。

プロジェクトだけで足したい語は .claude/ja-style-words.json に書く。
  {"hard": {"語": "言い換え"}, "soft": {...}, "exceptions": ["複合語", ...]}
"""
import hashlib
import json
import os
import re
import sys
import time

HOME = os.path.expanduser("~")
STATE = os.path.join(HOME, ".claude", ".ja-style-state.json")
ALLOW_DIR = os.path.join(".claude", "ja-style-allow")
ALLOW_TTL = 15 * 60
WORDS_FILE = os.path.join(".claude", "ja-style-words.json")
LOG = os.path.join(HOME, ".claude", ".ja-style-log")

# 誤検出しにくい語。常に差し戻す。
HARD = {
    "パリティ": "新旧で結果が一致すること／同じ結果になる",
    "象限": "組み合わせ／パターン（「4パターン」）",
    "契約違反": "仕様に反する／想定と違う値が来る",
    "骨組": "土台／大枠／スケルトン",
    "配管": "つなぎ／値を渡すだけの処理",
    "残置": "残したまま／消さずに置く",
    "残存": "残っている",
    "残骸": "使われなくなったコード",
    "追随": "合わせる／同じように直す",
    "全滅": "全部落ちた／全部失敗した",
    "根拠": "（使わない。調べた事実をそのまま書く）",
    "裏取": "事実確認",
    "転記": "写す",
    "棚卸": "洗い出し",
    "顕在化": "実際に起きる／表に出る",
    "明文": "はっきり書く",
    "未決事項": "未確定／決まっていないこと",
    "到達不能": "呼ばれない／通らない",
    "値域": "取りうる値",
    "未知値": "想定外の値",
    "負値": "マイナスの値",
    "ブロッカー": "ブロッキング／ブロッキングタスク",
    "符丁": "内輪の用語／そのプロジェクトでしか通じない言い方",
    "直交": "別々の軸で決まる／それぞれ独立している",
    "握手": "ハンドシェイク",
    "越境": "フレームをまたぐ／またいで渡す",
    "本線": "本来の経路／通常はこれを使う",
    "恒久策": "根本的な解決／根本的に直すには",
    "等価": "同じ／同じ状態になる",
    "温床": "起きやすい／ここで問題が出る",
    "人質": "引きずられる／待たされる",
    "本家": "最初に問題になった例／出どころ",
    "一次情報": "まず見る情報／確かな情報源",
    "実演": "実際にやってみる／動くコードで示す",
    "定石": "よく使われる手／普通はこうする",
    "逆用": "逆に利用する",
    "帰着": "たどり着く／原因は〜にある",
    "信頼の起点": "相手をどう信じるか",
    "帰結": "ここから決まること／その結果",
    "含意": "影響／意味するところ",
    "妥当性": "（使わない。何がどう問題ないのかを直接書く）",
    "裁量": "（使わない。誰が何を決めてよいのかを直接書く）",
    "黙って": "勝手に／突然／急に／報告せずに（何をしなかったのかで選ぶ）",
}

# 正当な使い方がある語。1回差し戻して、同じ内容の再実行は通す。
SOFT = {
    "契約": "インターフェース／仕様／受け渡しの決まり（商取引の契約ならそのままでよい）",
    "ゲート": "通す条件／チェック／ガード",
    "横断": "複数の〜にまたがる／〜をまとめて見る",
    "回帰": "デグレ／壊れる",
    "劣化": "悪くなる／遅くなる（数値があれば「〜ms 遅い」）",
    "照合": "突き合わせる／見比べる",
    "隔離": "切り離す／分ける",
    "マーク": "印を付ける／フラグを立てる／〜として扱う",
    "集約": "1か所にまとめる／〜に寄せる",
    "観測": "実際に見た／確認した",
    "匿名": "未ログイン／ゲスト",
    "規則": "ルール",
    "先行": "先に",
    "スナップショット": "（DB のスナップショットのみ。「その時点のデータ」の意味では使わない）",
    "窓": "枠／時間の範囲（「検索窓」など既存UIの名称のみ可）",
    "掘る": "詳しく見る／扱う",
    "集合": "決まったものだけ／一覧で決まっている",
    "交差": "両方で許されたものだけが通る／重なっている部分だけ",
    "主体": "オリジン／扱われる単位",
    "本質": "要点／実際に起きていること（「〜が本質です」で締めない）",
    "前提": "（役割を名指しせず、その条件をそのまま書く）",
    "論点": "（役割を名指しせず、何を決めたいのかをそのまま書く）",
    "観点": "（役割を名指しせず、何を見るのかをそのまま書く）",
    "解く": "パースする（本文から値を取り出す意味のとき）",
    "解け": "パースできた／パースできなかった",
    "解い": "パースした",
}

# 複合語として正当なもの。判定前に取り除く。
EXCEPTIONS = [
    "ゲートウェイ", "Gateway", "gateway",
    "ブックマーク", "マークアップ", "マークダウン", "ウォーターマーク",
    "回帰テスト", "回帰分析", "線形回帰",
    "検索窓",
    "掘り下げ",
    "横断的",
    "集合演算", "部分集合",
    "主体的",
    "匿名関数",
    "本質的",
    "命名規則",
    "契約中", "契約者", "契約数",
    "紐解", "打ち解け",
]

TEXT_EXT = {".md", ".markdown", ".mdx", ".txt"}
# ひらがな・カタカナ・漢字。漢字だけの語(「残骸」など)を取りこぼさないため漢字も入れる。
JP = re.compile("[぀-ヿ一-龿]")


def scrub(text, kana_only):
    text = re.sub(r"```.*?```", " ", text, flags=re.S)
    text = re.sub(r"`[^`\n]*`", " ", text)
    text = re.sub(r"https?://\S+", " ", text)
    if kana_only:
        text = "\n".join(l for l in text.split("\n") if JP.search(l))
    for e in EXCEPTIONS:
        text = text.replace(e, " ")
    return text


def lint(text, kana_only=False):
    t = scrub(text, kana_only)
    hard = [(w, s) for w, s in HARD.items() if w in t]
    soft = [(w, s) for w, s in SOFT.items() if w in t]
    return hard, soft


def search_dirs(cwd, rel):
    dirs = []
    # サブディレクトリで作業していてもプロジェクトルートの置き場を見つけられるよう、
    # 作業ディレクトリから上へ遡る。
    d = os.path.abspath(cwd) if cwd else ""
    for _ in range(8):
        if not d or d == os.path.dirname(d):
            break
        dirs.append(os.path.join(d, rel))
        if d == HOME:
            break
        d = os.path.dirname(d)
    for extra in (os.environ.get("CLAUDE_PROJECT_DIR", ""), HOME):
        if extra:
            dirs.append(os.path.join(extra, rel))
    return list(dict.fromkeys(dirs))


def load_project_words(cwd):
    for p in search_dirs(cwd, WORDS_FILE):
        try:
            d = json.load(open(p, encoding="utf-8"))
        except (OSError, ValueError):
            continue
        HARD.update(d.get("hard", {}))
        SOFT.update(d.get("soft", {}))
        EXCEPTIONS.extend(d.get("exceptions", []))


def allowed_words(cwd):
    """一時的に通す語を集める。

    .claude/ja-style-allow/ に、通したい語をファイル名にして touch する。
    置き場は作業ディレクトリから上へ遡って探すので、プロジェクトルートに
    置いておけばサブディレクトリで作業していても効く。~/.claude/ にも置ける。
    複数語は「,」「+」か空白で区切る。ALL と書けば全部通る。
    更新時刻から15分を過ぎたファイルは、その語を通さない。ファイル自体を
    消すのは期限が来た時点ではなく、次に hook が動いてこの関数がディレクトリを
    見たとき。hook が動かない間は残ったままになるが、残っていても通ることはない。
    touch し直すと更新時刻が今になり、そこからまた15分通る。
    """
    words = set()
    dirs = search_dirs(cwd, ALLOW_DIR)
    now = time.time()
    for d in dirs:
        try:
            names = os.listdir(d)
        except OSError:
            continue
        for n in names:
            if n.startswith(".") or n.lower() in ("readme", "readme.md"):
                continue
            f = os.path.join(d, n)
            try:
                if now - os.path.getmtime(f) > ALLOW_TTL:
                    os.remove(f)
                    note("期限切れで削除: %s" % f)
                    continue
            except OSError:
                continue
            for w in re.split(r"[,+\s]+", os.path.splitext(n)[0]):
                if w.strip():
                    words.add(w.strip())
    return words


def note(msg):
    """Stop hook が最新の返答を掴めているかを後から確かめるための記録。"""
    try:
        try:
            lines = open(LOG, encoding="utf-8").read().split("\n")
        except OSError:
            lines = []
        lines.append("%s %s" % (time.strftime("%Y-%m-%d %H:%M:%S"), msg))
        with open(LOG, "w", encoding="utf-8") as f:
            f.write("\n".join([l for l in lines if l.strip()][-40:]))
    except OSError:
        pass


def attempts(payload):
    """同じ内容が過去に何回差し戻されたかを返し、記録を1つ増やす。"""
    h = hashlib.sha256(payload.encode("utf-8")).hexdigest()
    try:
        state = json.load(open(STATE, encoding="utf-8"))
        if not isinstance(state, dict):
            state = {}
    except Exception:
        state = {}
    n = int(state.get(h, 0))
    state[h] = n + 1
    if len(state) > 200:
        state = dict(list(state.items())[-200:])
    try:
        with open(STATE, "w", encoding="utf-8") as f:
            json.dump(state, f)
    except OSError:
        pass
    return n


def judge(text, where, kana_only=False, allow=()):
    """差し戻すべきなら差し戻す。通してよければ何もせず返る。"""
    if any(w.upper() in ("ALL", "*") for w in allow):
        return
    hard, soft = lint(text, kana_only)
    hard = [(w, t) for w, t in hard if w not in allow]
    soft = [(w, t) for w, t in soft if w not in allow]
    if not (hard or soft):
        return
    n = attempts(text)
    if hard and n < 2:
        fail(hard, soft, where)
    if soft and n < 1:
        fail([], soft, where)


def report(hard, soft, where):
    out = ["「日本語の書き方」のルールに反する語が%sに残っています。" % where, ""]
    if hard:
        out.append("■ 必ず書き換える")
        for w, s in hard:
            out.append("  「%s」 → %s" % (w, s))
    if soft:
        out.append("■ 文脈しだい（正しい使い方ならそのまま同じ内容で再実行してよい）")
        for w, s in soft:
            out.append("  「%s」 → %s" % (w, s))
    out.append("")
    out.append("該当箇所を書き直してからやり直してください。")
    out.append("どうしても必要な語なら、同じ内容のまま再実行すれば通ります"
               "（必ず書き換える語は2回、文脈しだいの語は1回）。")
    out.append("正しい使い方だと分かっているなら "
               "touch .claude/ja-style-allow/<通したい語> でその語だけ15分通せます"
               "（15分を過ぎたら通らなくなります。ファイルが消えるのは"
               "その次に hook が動いたときです）。")
    return "\n".join(out)


def fail(hard, soft, where):
    sys.stderr.write(report(hard, soft, where) + "\n")
    sys.exit(2)


def _entries(path):
    rows = []
    try:
        for line in open(path, encoding="utf-8"):
            line = line.strip()
            if not line:
                continue
            try:
                d = json.loads(line)
            except ValueError:
                continue
            t = d.get("type")
            if t not in ("assistant", "user"):
                continue
            c = d.get("message", {}).get("content")
            if isinstance(c, str):
                txt = c
            elif isinstance(c, list):
                txt = "\n".join(b.get("text", "") for b in c
                                if isinstance(b, dict) and b.get("type") == "text")
            else:
                txt = ""
            rows.append((t, txt or ""))
    except OSError:
        return None
    return rows


def last_assistant_text(path, tries=10, wait=0.15):
    """最新の返答がトランスクリプトに書き出されるまで待ってから読む。

    書き出しは返答の生成と競合するので、待たずに読むと1つ前の返答を
    掴んでしまう。最後の user 行より後ろに assistant のテキストが
    現れたときだけ、それを最新とみなす。
    """
    for _ in range(tries):
        rows = _entries(path)
        if rows is None:
            return None
        last_user = max((i for i, (t, _) in enumerate(rows) if t == "user"), default=-1)
        cand = [(i, x) for i, (t, x) in enumerate(rows) if t == "assistant" and x.strip()]
        if cand and cand[-1][0] > last_user:
            note("Stop: 最新の返答を取得 (%d文字)" % len(cand[-1][1]))
            return cand[-1][1]
        time.sleep(wait)
    note("Stop: 最新の返答が書き出されず断念 (assistant=%s < user=%s)"
         % (cand[-1][0] if cand else -1, last_user))
    return None


GH_WRITE = re.compile(r"\bgh\s+(pr|issue)\s+(create|edit|comment|review)\b")

# 書き込む側の MCP ツール。idea の apply_patch/create_new_file、
# Confluence のページ作成、Slack の送信などがここに入る。検索や読み取りは外す。
MCP_WRITE = re.compile(
    r"(write|edit|patch|create|update|replace|append|comment|post|send|upload|rename)", re.I)

# 書き込みを伴いそうな形。Write/Edit を通さず Bash から直接書く経路をここで拾う。
WRITEISH = re.compile(
    r"<<|>|\btee\b|\bsed\b[^|]*-i|\bgit\s+commit\b"
    r"|\bgh\s+(pr|issue)\s+(create|edit|comment|review)\b")


def _strings(v):
    """tool_input に入っている文字列を全部集める。"""
    out = []
    if isinstance(v, str):
        out.append(v)
    elif isinstance(v, dict):
        for x in v.values():
            out.extend(_strings(x))
    elif isinstance(v, list):
        for x in v:
            out.extend(_strings(x))
    return out


RULE_PATH = re.compile(r"/\.?claude/(hooks|rules)/|CLAUDE\.md|ja-style-words\.json")


def exempt(path):
    if not path:
        return False
    return bool(RULE_PATH.search(path))


def main():
    try:
        data = json.load(sys.stdin)
    except Exception:
        return
    event = data.get("hook_event_name", "")
    load_project_words(data.get("cwd", ""))
    allow = allowed_words(data.get("cwd", ""))

    if event == "Stop":
        if data.get("stop_hook_active"):
            return
        text = last_assistant_text(data.get("transcript_path", ""))
        if not text:
            return
        judge(text, "返答", False, allow)
        return

    if event != "PreToolUse":
        return

    tool = data.get("tool_name", "")
    ti = data.get("tool_input", {}) or {}

    if tool == "Bash":
        cmd = ti.get("command", "") or ""
        if RULE_PATH.search(cmd):
            return
        if not (JP.search(cmd) and WRITEISH.search(cmd)):
            return
        body = cmd
        m = re.search(r"--body-file[= ]+(\S+)", cmd)
        if m:
            p = m.group(1).strip("'\"")
            try:
                body += "\n" + open(p, encoding="utf-8").read()
            except OSError:
                pass
        kana_only = False
        where = "PR / Issue の本文" if GH_WRITE.search(cmd) else "コマンドで書き込む内容"
    elif tool.startswith("mcp__") and MCP_WRITE.search(tool):
        body = "\n".join(_strings(ti))
        if not JP.search(body):
            return
        kana_only = False
        where = tool
    elif tool in ("Write", "Edit", "NotebookEdit"):
        path = ti.get("file_path") or ti.get("notebook_path") or ""
        if exempt(path):
            return
        body = ti.get("content") or ti.get("new_string") or ti.get("new_source") or ""
        if not body:
            return
        ext = os.path.splitext(path)[1].lower()
        kana_only = ext not in TEXT_EXT
        where = os.path.basename(path) or "書き込み内容"
    else:
        return

    judge(body, where, kana_only, allow)


if __name__ == "__main__":
    main()
