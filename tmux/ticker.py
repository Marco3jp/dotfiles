#!/usr/bin/env python3
"""tmux のステータス行にニュースと天気を横スクロールで流す。

  ticker.py render <幅>        表示する <幅> 桁ぶんの文字列を出す（tmux の #() から毎秒呼ぶ）
  ticker.py render-desc <幅>   左端にかかっている記事の概要を出す
  ticker.py fetch              NHK ニュースと気象庁の予報を取り直してキャッシュに書く

render はキャッシュが古ければ fetch を裏で起動するので、cron などは要らない。
"""
import datetime
import email.utils
import json
import os
import subprocess
import sys
import time
import unicodedata
import urllib.request
import xml.etree.ElementTree as ET

# 気象庁の府県予報区コード（130000=東京都, 270000=大阪府 など）。予報区の先頭の地域を表示する
JMA_OFFICE = os.environ.get("TICKER_JMA_OFFICE", "130000")
# NHK のカテゴリをカンマ区切りで
# （cat0=主要, cat1=社会, cat2=暮らし, cat3=科学・文化, cat4=政治, cat5=経済, cat6=国際, cat7=スポーツ, cat9=最新15項目）
NHK_CATEGORIES = os.environ.get("TICKER_NHK_CATEGORY", "cat4,cat5,cat6").split(",")
NEWS_COUNT = 30
REFRESH_SEC = 600
# 1 秒あたりに進める桁数。全角 1 文字は 2 桁
SPEED = int(os.environ.get("TICKER_SPEED", "6"))
SEPARATOR = "   ◆   "

CACHE_DIR = os.path.join(os.path.expanduser("~/.cache"), "tmux-ticker")
NEWS_FILE = os.path.join(CACHE_DIR, "news.json")
WEATHER_FILE = os.path.join(CACHE_DIR, "weather.txt")
STAMP_FILE = os.path.join(CACHE_DIR, "fetched_at")
LOCK_FILE = os.path.join(CACHE_DIR, "lock")

JST = datetime.timezone(datetime.timedelta(hours=9))


def http_get(url):
    req = urllib.request.Request(url, headers={"User-Agent": "tmux-ticker"})
    with urllib.request.urlopen(req, timeout=10) as res:
        return res.read()


def fetch_news():
    items = {}
    for cat in NHK_CATEGORIES:
        root = ET.fromstring(http_get(f"https://www.nhk.or.jp/rss/news/{cat.strip()}.xml"))
        for item in root.iterfind("./channel/item"):
            title = (item.findtext("title") or "").strip()
            if title:
                items[title] = (
                    email.utils.parsedate_to_datetime(item.findtext("pubDate")),
                    " ".join((item.findtext("description") or "").split()),
                )
    titles = sorted(items, key=lambda t: items[t][0], reverse=True)[:NEWS_COUNT]
    return json.dumps([{"title": t, "description": items[t][1]} for t in titles], ensure_ascii=False)


def day_label(d, today):
    name = {0: "今日", 1: "明日", 2: "明後日"}.get((d - today).days, f"{d.month}/{d.day}")
    return f"{name}({d.day}日)"


def group_by_date(series, key):
    out = {}
    for t, v in zip(series["timeDefines"], series["areas"][0][key]):
        dt = datetime.datetime.fromisoformat(t)
        out.setdefault(dt.date(), []).append((dt.hour, v))
    return out


def fetch_weather():
    data = json.loads(http_get(f"https://www.jma.go.jp/bosai/forecast/data/forecast/{JMA_OFFICE}.json"))
    series = data[0]["timeSeries"]
    weathers = group_by_date(series[0], "weathers")
    pops = group_by_date(series[1], "pops")
    # 0 時の値が朝の最低気温、9 時の値が日中の最高気温
    temps = group_by_date(series[2], "temps") if len(series) > 2 else {}

    today = datetime.datetime.now(JST).date()
    parts = []
    for d in sorted(weathers)[:2]:
        line = f"{day_label(d, today)} {' '.join(weathers[d][0][1].split())}"
        t = dict(temps.get(d, []))
        if t.get(0) and t.get(9) and t[0] != t[9]:
            line += f" {t[0]}/{t[9]}℃"
        elif t.get(9):
            line += f" 最高{t[9]}℃"
        p = [v for _, v in pops.get(d, []) if v]
        if p:
            line += f" 降水{'/'.join(p)}%"
        parts.append(line)
    area = series[0]["areas"][0]["area"]["name"]
    return f"{area}  " + SEPARATOR.join(parts)


def write_atomic(path, text):
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        f.write(text)
    os.replace(tmp, path)


def fetch():
    os.makedirs(CACHE_DIR, exist_ok=True)
    # 失敗した側は前回の内容を残す
    for path, fn in ((WEATHER_FILE, fetch_weather), (NEWS_FILE, fetch_news)):
        try:
            write_atomic(path, fn())
        except Exception as e:
            print(f"{fn.__name__}: {e}", file=sys.stderr)
    write_atomic(STAMP_FILE, str(int(time.time())))


def mtime(path):
    try:
        return os.path.getmtime(path)
    except OSError:
        return 0


def spawn_fetch_if_stale():
    now = time.time()
    if now - mtime(STAMP_FILE) < REFRESH_SEC or now - mtime(LOCK_FILE) < 60:
        return
    os.makedirs(CACHE_DIR, exist_ok=True)
    write_atomic(LOCK_FILE, "")
    subprocess.Popen(
        [sys.executable, os.path.abspath(__file__), "fetch"],
        stdin=subprocess.DEVNULL,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        start_new_session=True,
    )


def read(path):
    try:
        with open(path, encoding="utf-8") as f:
            return f.read().strip()
    except OSError:
        return ""


def load_items():
    """流す項目を [(見出し, 概要)] で返す。天気は概要なし"""
    items = []
    weather = read(WEATHER_FILE)
    if weather:
        items.append((weather, ""))
    try:
        items += [(n["title"], n["description"]) for n in json.loads(read(NEWS_FILE))]
    except ValueError:
        pass
    if not items:
        items.append(("ニュースと天気を取得中…", ""))
    return items


def is_wide(c):
    return unicodedata.east_asian_width(c) in "WF"


def escape(s):
    # tmux は #() の出力に含まれる #[...] や #{...} を解釈するので潰しておく
    return s.replace("#", "＃")


def build_cells(items):
    """1 桁 = 1 要素の (文字, 項目番号, 見出しか) の列。全角文字の右半分は文字を None にする"""
    cells = []
    for i, (title, _) in enumerate(items):
        # 区切りは直前の項目に含める。区切りが左端にある間は直前の項目のまま
        for c, is_title in [(c, True) for c in escape(title)] + [(c, False) for c in SEPARATOR]:
            cells.append((c, i, is_title))
            if is_wide(c):
                cells.append((None, i, is_title))
    return cells


def visible_window(width):
    """今の時刻で見えている <幅> 桁ぶんのセルと、左端にかかっている項目番号を返す"""
    items = load_items()
    cells = build_cells(items)
    unit = len(cells)
    while len(cells) < width:
        cells += cells[:unit]
    start = (int(time.time()) * SPEED) % unit
    window = (cells + cells)[start:start + width]
    return items, window, window[0][1]


def render(width):
    spawn_fetch_if_stale()
    _, window, current = visible_window(width)
    out = []
    bold = False
    for pos, (c, i, is_title) in enumerate(window):
        if c is None:
            # 端で全角文字が半分に切れたら空白で埋める
            if pos == 0:
                out.append(" ")
            continue
        if pos == len(window) - 1 and is_wide(c):
            c = " "
        want = i == current and is_title
        if want != bold:
            out.append("#[bold]" if want else "#[nobold]")
            bold = want
        out.append(c)
    if bold:
        out.append("#[nobold]")
    print("".join(out))


def render_desc(width):
    items, _, current = visible_window(width)
    out = []
    used = 0
    for c in escape(items[current][1]):
        w = 2 if is_wide(c) else 1
        if used + w > width:
            break
        out.append(c)
        used += w
    print("".join(out))


def main():
    if len(sys.argv) >= 2 and sys.argv[1] == "fetch":
        fetch()
    elif len(sys.argv) >= 3 and sys.argv[1] == "render":
        render(int(sys.argv[2]))
    elif len(sys.argv) >= 3 and sys.argv[1] == "render-desc":
        render_desc(int(sys.argv[2]))
    else:
        print(__doc__, file=sys.stderr)
        sys.exit(2)


if __name__ == "__main__":
    main()
