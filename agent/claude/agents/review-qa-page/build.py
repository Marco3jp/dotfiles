#!/usr/bin/env python3
import json
import re
import shutil
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
TEMPLATE = HERE / "template.html"


def norm(s):
    """空白の違いだけ吸収して比較するための正規化"""
    return re.sub(r"[\s　]+", "", str(s or ""))


def main():
    if len(sys.argv) != 3:
        print("usage: build.py <data.json> <out.html>", file=sys.stderr)
        return 2

    data_path = Path(sys.argv[1])
    out_path = Path(sys.argv[2])

    data = json.loads(data_path.read_text(encoding="utf-8"))

    meta = data.get("meta") or {}
    items = data.get("items") or []
    if not items:
        print("error: items is empty", file=sys.stderr)
        return 1

    seen = set()
    for i, item in enumerate(items):
        qid = item.get("id")
        if not qid:
            print(f"error: items[{i}] has no id", file=sys.stderr)
            return 1
        if qid in seen:
            print(f"error: duplicated id {qid!r}", file=sys.stderr)
            return 1
        seen.add(qid)
        if not item.get("question"):
            print(f"error: {qid} has no question", file=sys.stderr)
            return 1
        for j, ref in enumerate(item.get("refs") or []):
            kind = ref.get("kind")
            if kind not in ("code", "schema", "confluence", "github", "link", "note"):
                print(f"error: {qid} refs[{j}] has invalid kind {kind!r}", file=sys.stderr)
                return 1
            if kind in ("code", "schema") and ref.get("snippet") and not ref.get("startLine"):
                print(f"error: {qid} refs[{j}] needs startLine", file=sys.stderr)
                return 1

    if not meta.get("id"):
        meta["id"] = out_path.parent.name or "qa"
    data["meta"] = meta

    # 質問文が原文どおりかを照合する（Sonnet が言い換え・要約していないかの検査）
    source = meta.get("sourceText")
    drifted = []
    if source:
        haystack = norm(source)
        for item in items:
            ok = norm(item["question"]) in haystack
            item["verbatim"] = ok
            if not ok:
                drifted.append(item["id"])
    else:
        print(
            "warn: meta.sourceText が無いので原文照合ができない。"
            "渡された確認事項の原文を meta.sourceText に入れること",
            file=sys.stderr,
        )

    payload = json.dumps(data, ensure_ascii=False, separators=(",", ":"))
    payload = payload.replace("</", "<\\/")

    title = meta.get("title") or "確認事項"
    html = TEMPLATE.read_text(encoding="utf-8")
    if "__QA_DATA_JSON__" not in html:
        print("error: template placeholder not found", file=sys.stderr)
        return 1
    html = html.replace("__QA_TITLE__", title.replace("<", "&lt;").replace("&", "&amp;"))
    html = html.replace("__QA_DATA_JSON__", payload)

    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(html, encoding="utf-8")
    kept = out_path.parent / "data.json"
    if kept.resolve() != data_path.resolve():
        shutil.copyfile(data_path, kept)

    refs = sum(len(it.get("refs") or []) for it in items)
    resolved = sum(
        1
        for it in items
        for r in (it.get("refs") or [])
        if r.get("snippet") or r.get("excerpt")
    )
    print(f"built: {out_path}")
    print(f"items={len(items)} refs={refs} with_body={resolved} bytes={out_path.stat().st_size}")
    if source:
        print(f"verbatim={len(items) - len(drifted)}/{len(items)}")
        if drifted:
            print(
                "warn: 原文と一致しない質問文がある -> " + ", ".join(drifted)
                + "（原文をそのまま question に入れ直すこと。補足は note へ）",
                file=sys.stderr,
            )
    return 0


if __name__ == "__main__":
    sys.exit(main())
