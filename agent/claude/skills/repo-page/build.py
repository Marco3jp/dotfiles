#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""ディレクトリ配下のファイルを1ファイル完結のHTMLファイルブラウザにする。

  build.py <src-dir> [-o out.html] [--title T] [--subtitle S]
           [--exclude GLOB ...] [--include GLOB ...] [--allow PATH ...]
           [--max-file-bytes N] [--max-image-bytes N] [--preview-lines N]
           [--entry PATH] [--print-json]
"""
import argparse
import base64
import fnmatch
import json
import os
import re
import subprocess
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
TEMPLATE = HERE / "template.html"
JST = timezone(timedelta(hours=9))

SKIP_DIR_NAMES = {
    ".git", ".hg", ".svn", "node_modules", ".venv", "venv", "__pycache__",
    ".pytest_cache", ".mypy_cache", ".ruff_cache", ".ipynb_checkpoints",
    "site-packages", ".terraform", ".gradle", ".tox", ".eggs", "htmlcov",
    ".idea", ".vscode", ".cache", ".parcel-cache", ".turbo", ".svelte-kit",
    "dist", "build", ".next", ".nuxt", ".output", "coverage", "target",
    ".claude-trace",
}
SKIP_DIR_GLOBS = ["*.egg-info", "*.dSYM", "*.xcworkspace"]

SKIP_FILE_GLOBS = [
    ".DS_Store", "Thumbs.db", "desktop.ini", ".gitkeep",
    "*.pyc", "*.pyo", "*.pyd", "*.so", "*.dylib", "*.dll", "*.o", "*.a",
    "*.class", "*.jar", "*.wasm", "*.bin", "*.dat",
    "*.zip", "*.gz", "*.tgz", "*.bz2", "*.xz", "*.7z", "*.rar",
    "*.mp4", "*.mov", "*.avi", "*.webm", "*.mp3", "*.wav", "*.m4a",
    "*.ttf", "*.otf", "*.woff", "*.woff2", "*.eot", "*.afm", "*.pfb",
    "*.sqlite", "*.sqlite3", "*.db", "*.parquet", "*.pkl", "*.npy", "*.npz",
    "*.feather", "*.arrow", "*.avro",
    "*.map", "*.har", "*.min.js", "*.min.css", "*.lock",
    "package-lock.json", "yarn.lock", "pnpm-lock.yaml", "go.sum",
    "*.tfstate", "*.tfstate.*", "*.orig", "*.rej", "*.swp",
]

SECRET_PATH_GLOBS = [
    ".env", ".env.*", "*.env", ".envrc", "*.pem", "*.key", "*.p8", "*.p12",
    "*.pfx", "*.keystore", "*.jks", "id_rsa*", "id_ed25519*", ".netrc",
    ".pgpass", ".npmrc", ".pypirc", ".htpasswd", "credentials", "credentials.*",
    "*credential*.json", "*secret*.json", "*secret*.yaml", "*secret*.yml",
    "*service-account*.json", "*service_account*.json", "client_secret*.json",
    "*.kubeconfig", "kubeconfig",
]

SECRET_PATTERNS = [
    ("秘密鍵", re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----")),
    ("AWSアクセスキー", re.compile(r"\b(?:AKIA|ASIA)[0-9A-Z]{16}\b")),
    ("GitHubトークン", re.compile(r"\b(?:gh[pousr]_[A-Za-z0-9]{28,}|github_pat_[A-Za-z0-9_]{40,})")),
    ("Slackトークン", re.compile(r"\bxox[baprse]-[A-Za-z0-9-]{12,}")),
    ("APIキー(sk-)", re.compile(r"\bsk-(?:ant-)?[A-Za-z0-9_-]{24,}")),
    ("Google APIキー", re.compile(r"\bAIza[0-9A-Za-z_-]{35}\b")),
    ("GCPサービスアカウント鍵", re.compile(r'"type"\s*:\s*"service_account"')),
    ("JWT", re.compile(r"\beyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}")),
    ("接続文字列のパスワード", re.compile(r"\b(?:mysql|postgres(?:ql)?|mongodb(?:\+srv)?|redis|amqp)://[^\s:@/]+:[^\s:@/]{3,}@")),
]

SUSPECT_PATTERNS = [
    ("パスワードらしい値", re.compile(
        r"(?i)\b(?:password|passwd|pwd|secret|api[_-]?key|access[_-]?token|auth[_-]?token)\b\s*[:=]\s*[\"']?[^\s\"',#;)]{8,}"), 1),
    ("メールアドレス", re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b"), 5),
    ("電話番号", re.compile(r"(?<![\d-])0\d{1,3}-\d{2,4}-\d{4}(?![\d-])"), 5),
]

MARKDOWN_EXTS = {".md", ".markdown", ".mdx"}
CSV_EXTS = {".csv", ".tsv"}
HTML_EXTS = {".html", ".htm"}
IMAGE_MIME = {
    ".png": "image/png", ".jpg": "image/jpeg", ".jpeg": "image/jpeg",
    ".gif": "image/gif", ".webp": "image/webp", ".svg": "image/svg+xml",
    ".avif": "image/avif", ".ico": "image/x-icon", ".bmp": "image/bmp",
}
OPAQUE_EXTS = {
    ".pdf": "PDF", ".xlsx": "Excel", ".xls": "Excel", ".docx": "Word",
    ".pptx": "PowerPoint", ".numbers": "Numbers", ".key": "Keynote",
}
LANG_BY_EXT = {
    ".py": "python", ".sql": "sql", ".js": "javascript", ".mjs": "javascript",
    ".cjs": "javascript", ".ts": "typescript", ".tsx": "tsx", ".jsx": "jsx",
    ".vue": "vue", ".go": "go", ".php": "php", ".rb": "ruby", ".sh": "bash",
    ".zsh": "bash", ".bash": "bash", ".json": "json", ".yaml": "yaml",
    ".yml": "yaml", ".toml": "toml", ".ini": "ini", ".cfg": "ini",
    ".html": "html", ".htm": "html", ".css": "css", ".scss": "scss",
    ".xml": "xml", ".graphql": "graphql", ".gql": "graphql", ".tf": "terraform",
    ".swift": "swift", ".kt": "kotlin", ".java": "java", ".rs": "rust",
    ".csv": "csv", ".tsv": "csv", ".md": "markdown", ".txt": "text",
    ".ipynb": "json", ".r": "r", ".proto": "proto", ".mk": "makefile",
}
NAME_LANG = {
    "Makefile": "makefile", "Dockerfile": "docker", "Procfile": "text",
    ".gitignore": "text", ".dockerignore": "text", ".editorconfig": "ini",
}


def human(n):
    if n < 1024:
        return f"{n} B"
    if n < 1024 * 1024:
        return f"{n / 1024:.1f} KB"
    return f"{n / 1024 / 1024:.2f} MB"


def match_any(name, globs):
    return any(fnmatch.fnmatch(name, g) for g in globs)


class Git:
    def __init__(self):
        self.roots = {}
        self.info = {}

    def _run(self, cwd, args):
        try:
            out = subprocess.run(["git", "-C", str(cwd)] + args,
                                 capture_output=True, text=True, timeout=15)
        except (OSError, subprocess.SubprocessError):
            return None
        if out.returncode != 0:
            return None
        return out.stdout.strip()

    def root_of(self, directory):
        directory = str(directory)
        if directory in self.roots:
            return self.roots[directory]
        top = self._run(directory, ["rev-parse", "--show-toplevel"])
        self.roots[directory] = top
        return top

    def info_of(self, top):
        if top in self.info:
            return self.info[top]
        remote = self._run(top, ["remote", "get-url", "origin"]) or ""
        sha = self._run(top, ["rev-parse", "HEAD"]) or ""
        tracked = self._run(top, ["ls-files", "-z"]) or ""
        web = ""
        m = re.match(r"(?:git@([^:]+):|https?://(?:[^@/]+@)?([^/]+)/)(.+?)(?:\.git)?/?$", remote)
        if m and sha:
            host = m.group(1) or m.group(2)
            slug = m.group(3)
            if "github" in host:
                web = f"https://{host}/{slug}/blob/{sha}/"
        got = {
            "remote": remote,
            "sha": sha,
            "web": web,
            "tracked": set(p for p in tracked.split("\0") if p),
            "slug": (m.group(3) if m else ""),
        }
        self.info[top] = got
        return got

    def url_for(self, path):
        top = self.root_of(path.parent)
        if not top:
            return "", ""
        got = self.info_of(top)
        if not got["web"]:
            return "", got["slug"]
        try:
            rel = path.resolve().relative_to(Path(top).resolve()).as_posix()
        except ValueError:
            return "", got["slug"]
        if got["tracked"] and rel not in got["tracked"]:
            return "", got["slug"]
        return got["web"] + rel, got["slug"]


def classify(path):
    ext = path.suffix.lower()
    if ext in MARKDOWN_EXTS:
        return "markdown"
    if ext in IMAGE_MIME:
        return "image"
    if ext in HTML_EXTS:
        return "html"
    if ext in CSV_EXTS:
        return "csv"
    if ext in OPAQUE_EXTS:
        return "opaque"
    return "text"


def lang_of(path):
    if path.name in NAME_LANG:
        return NAME_LANG[path.name]
    return LANG_BY_EXT.get(path.suffix.lower(), "")


def read_text(path):
    raw = path.read_bytes()
    if b"\0" in raw[:8000]:
        return None, raw
    for enc in ("utf-8", "cp932", "euc-jp"):
        try:
            return raw.decode(enc), raw
        except UnicodeDecodeError:
            continue
    return raw.decode("utf-8", errors="replace"), raw


def scan_secrets(text):
    hits = []
    for name, pat in SECRET_PATTERNS:
        if pat.search(text):
            hits.append(name)
    return hits


def scan_suspects(text):
    hits = []
    for name, pat, threshold in SUSPECT_PATTERNS:
        n = len(pat.findall(text))
        if n >= threshold:
            hits.append(f"{name}×{n}")
    return hits


def collect(src, args):
    files = []
    skipped = []
    git = Git()
    slug = ""
    total_bytes = 0

    for dirpath, dirnames, filenames in os.walk(src):
        dirnames[:] = sorted(
            d for d in dirnames
            if d not in SKIP_DIR_NAMES and not match_any(d, SKIP_DIR_GLOBS)
            and not os.path.islink(os.path.join(dirpath, d))
        )
        for filename in sorted(filenames):
            path = Path(dirpath) / filename
            rel = path.relative_to(src).as_posix()
            if args.include and not match_any(rel, args.include) and not match_any(filename, args.include):
                continue
            if match_any(rel, args.exclude) or match_any(filename, args.exclude):
                skipped.append((rel, "除外指定"))
                continue
            allowed = rel in args.allow
            if not allowed and (match_any(filename, SKIP_FILE_GLOBS) or match_any(rel, SKIP_FILE_GLOBS)):
                skipped.append((rel, "対象外の種類"))
                continue
            try:
                size = path.stat().st_size
            except OSError:
                skipped.append((rel, "読めない"))
                continue

            entry = {
                "path": rel,
                "name": filename,
                "dir": str(Path(rel).parent) if str(Path(rel).parent) != "." else "",
                "ext": path.suffix.lower().lstrip("."),
                "bytes": size,
                "kind": classify(path),
                "lang": lang_of(path),
                "status": "ok",
            }
            url, found_slug = git.url_for(path)
            slug = slug or found_slug
            if url:
                entry["url"] = url

            if not allowed and match_any(filename, SECRET_PATH_GLOBS):
                entry.update(kind="blocked", status="blocked",
                             reason="鍵やトークンが入りうる名前なので中身を載せていない")
                files.append(entry)
                continue

            if entry["kind"] == "opaque":
                entry.update(status="omitted",
                             reason=f"{OPAQUE_EXTS[path.suffix.lower()]} はページ上で開けない")
                files.append(entry)
                continue

            if entry["kind"] == "image":
                if size > args.max_image_bytes:
                    entry.update(status="omitted",
                                 reason=f"画像が大きい（{human(size)} > {human(args.max_image_bytes)}）")
                else:
                    mime = IMAGE_MIME[path.suffix.lower()]
                    b64 = base64.b64encode(path.read_bytes()).decode("ascii")
                    entry["dataUri"] = f"data:{mime};base64,{b64}"
                    total_bytes += len(b64)
                files.append(entry)
                continue

            text, raw = read_text(path)
            if text is None:
                entry.update(status="omitted", reason="テキストではない")
                files.append(entry)
                continue

            if not allowed:
                hits = scan_secrets(text)
                if hits:
                    entry.update(kind="blocked", status="blocked",
                                 reason="中身に " + " / ".join(hits) + " らしい文字列がある")
                    files.append(entry)
                    continue
                suspects = scan_suspects(text)
                if suspects:
                    entry["suspect"] = suspects

            lines = text.count("\n") + (0 if text.endswith("\n") or not text else 1)
            entry["lines"] = lines
            if size > args.max_file_bytes:
                head = text.split("\n")[: args.preview_lines]
                entry["content"] = "\n".join(head)
                entry.update(status="truncated",
                             reason=f"先頭 {len(head)} 行だけ載せている（全体 {lines} 行 / {human(size)}）")
            else:
                entry["content"] = text
            total_bytes += len(entry.get("content", ""))
            files.append(entry)

    return files, skipped, slug, total_bytes


def pick_entry(files, wanted):
    live = [f for f in files if f.get("content") or f.get("dataUri")]
    if wanted:
        for f in live:
            if f["path"] == wanted:
                return f["path"]
    for name in ("README.md", "readme.md", "README.markdown", "index.md"):
        for f in live:
            if f["path"] == name:
                return f["path"]
    roots = [f for f in live if not f["dir"] and f["kind"] == "markdown"]
    if roots:
        return max(roots, key=lambda f: f["bytes"])["path"]
    mds = [f for f in live if f["kind"] == "markdown"]
    if mds:
        return max(mds, key=lambda f: f["bytes"])["path"]
    return live[0]["path"] if live else ""


def title_from(files, src):
    for f in files:
        if f["path"].lower() in ("readme.md", "readme.markdown", "index.md"):
            for line in (f.get("content") or "").split("\n"):
                if line.startswith("# "):
                    return line[2:].strip()
    return src.name


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("src")
    ap.add_argument("-o", "--out")
    ap.add_argument("--title")
    ap.add_argument("--subtitle", default="")
    ap.add_argument("--source", default="")
    ap.add_argument("--entry", default="")
    ap.add_argument("--exclude", action="append", default=[])
    ap.add_argument("--include", action="append", default=[])
    ap.add_argument("--allow", action="append", default=[])
    ap.add_argument("--max-file-bytes", type=int, default=262144)
    ap.add_argument("--max-image-bytes", type=int, default=1572864)
    ap.add_argument("--preview-lines", type=int, default=200)
    ap.add_argument("--print-json")
    ap.add_argument("--force", action="store_true")
    args = ap.parse_args()

    src = Path(args.src).resolve()
    if not src.is_dir():
        sys.exit(f"error: ディレクトリではない: {src}")
    args.allow = set(args.allow)

    out = Path(args.out).resolve() if args.out else (src / "repo-page.html").resolve()
    if out.exists() and not args.force:
        sys.exit(f"error: すでにある: {out}\n  別の -o を渡すか --force を付ける")
    try:
        args.exclude.append(out.relative_to(src).as_posix())
    except ValueError:
        pass

    files, skipped, slug, payload_bytes = collect(src, args)
    if not files:
        sys.exit("error: 載せられるファイルがなかった")

    entry = pick_entry(files, args.entry)
    title = args.title or title_from(files, src)

    counts = {}
    for f in files:
        key = f["kind"] if f["status"] == "ok" else f["status"]
        counts[key] = counts.get(key, 0) + 1

    data = {
        "meta": {
            "title": title,
            "subtitle": args.subtitle,
            "source": args.source or f"{slug or src.parent.name}/{src.name}",
            "root": src.name,
            "generatedAt": datetime.now(JST).strftime("%Y-%m-%d %H:%M"),
            "entry": entry,
            "counts": counts,
            "totalBytes": sum(f["bytes"] for f in files),
        },
        "files": files,
    }

    tpl = TEMPLATE.read_text(encoding="utf-8")
    blob = json.dumps(data, ensure_ascii=False, separators=(",", ":"))
    blob = blob.replace("<", "\\u003c").replace("\u2028", "\\u2028").replace("\u2029", "\\u2029")
    html = tpl.replace("__REPO_PAGE_TITLE__", title.replace("<", "&lt;"))
    html = html.replace("__REPO_PAGE_DATA__", blob)

    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(html, encoding="utf-8")
    if args.print_json:
        Path(args.print_json).write_text(
            json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")

    out_size = out.stat().st_size
    print(f"出力: {out}  ({human(out_size)})")
    print(f"ファイル: {len(files)}件  " + " / ".join(f"{k} {v}" for k, v in sorted(counts.items())))
    print(f"最初に開く: {entry}")
    if skipped:
        kinds = {}
        for _, why in skipped:
            kinds[why] = kinds.get(why, 0) + 1
        print("載せなかった: " + " / ".join(f"{k} {v}件" for k, v in sorted(kinds.items())))
    for f in files:
        if f["status"] == "blocked":
            print(f"  除いた: {f['path']} — {f['reason']}")
    for f in files:
        if f["status"] in ("truncated", "omitted"):
            print(f"  一部だけ: {f['path']} — {f['reason']}")
    for f in files:
        if f.get("suspect"):
            print(f"  要確認: {f['path']} — {' / '.join(f['suspect'])}")
    if out_size > 15 * 1024 * 1024:
        print("警告: Artifact の上限16MBを超えるおそれがある。--max-file-bytes を下げるか --exclude で絞る")
    elif out_size > 12 * 1024 * 1024:
        print("注意: 出力が12MBを超えた。画像や大きいCSVを絞ると軽くなる")


if __name__ == "__main__":
    main()
