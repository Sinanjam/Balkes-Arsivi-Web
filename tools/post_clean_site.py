#!/usr/bin/env python3
from __future__ import annotations

import html
import json
import re
import sys
from pathlib import Path
from typing import Any

OUT = Path(sys.argv[1]).resolve() if len(sys.argv) > 1 else Path("public").resolve()
ITEMS = OUT / "data" / "items.json"

URL_RE = re.compile(r"https?://\S+", re.I)
IMG_RE = re.compile(r"\.(png|jpg|jpeg|webp|gif)(\?.*)?$", re.I)
BAD_RE = re.compile(r"(balkesarsivi\.com|web\.archive\.org|/user/cimage/|cimage/|\.gif|\.jpg|\.jpeg|\.png|\.webp)", re.I)

WORD_RE = re.compile(r"[A-Za-zÇĞİÖŞÜçğıöşü]{3,}")

def clean(s: Any) -> str:
    s = "" if s is None else html.unescape(str(s))
    s = re.sub(r"\r\n?", "\n", s)
    s = re.sub(r"(?i)Kayıp\s+Sayfalar\s*: ?", "", s)
    s = re.sub(r"(?im)^\s*#{1,6}\s*Tablolar\s*$", "", s)
    s = re.sub(r"(?im)^\s*#{1,6}\s*Tablo\s+\d+\s*$", "", s)
    s = re.sub(r"[ \t]+", " ", s)
    s = re.sub(r"\n{3,}", "\n\n", s)
    return s.strip()

def useful_words(s: str) -> int:
    s = URL_RE.sub(" ", s)
    s = re.sub(r"[\w./:-]+\.(png|jpg|jpeg|webp|gif)", " ", s, flags=re.I)
    return len(WORD_RE.findall(s))

def is_image_or_url_line(s: str) -> bool:
    t = clean(s)
    if not t:
        return True
    if URL_RE.fullmatch(t):
        return True
    if IMG_RE.search(t) and ("/" in t or "http" in t.lower() or "cimage" in t.lower()):
        return True
    if BAD_RE.search(t) and useful_words(t) < 6:
        return True
    return False

def strip_bad_lines(s: str) -> str:
    lines = []
    for raw in re.split(r"\n+", clean(s)):
        line = clean(raw)
        if not line:
            continue
        if is_image_or_url_line(line):
            continue
        without_urls = URL_RE.sub("", line).strip()
        if len(without_urls) < 20 and BAD_RE.search(line):
            continue
        lines.append(without_urls or line)
    return clean("\n\n".join(lines))

def looks_bad_item(item: dict[str, Any]) -> bool:
    title = clean(item.get("title", ""))
    summary = clean(item.get("summary", ""))
    text = clean(item.get("text", ""))
    sample = clean("\n".join([title, summary, text[:500]]))

    if not title:
        return True
    if is_image_or_url_line(title):
        return True
    if useful_words(sample) < 6:
        return True
    if BAD_RE.search(sample) and useful_words(sample) < 24:
        return True

    url_len = sum(len(m.group(0)) for m in URL_RE.finditer(sample))
    bad_hits = len(BAD_RE.findall(sample))
    noise = (url_len + bad_hits * 45) / max(1, len(sample))
    if noise > 0.24 and useful_words(sample) < 60:
        return True
    return False

def clean_item(item: dict[str, Any]) -> dict[str, Any] | None:
    if looks_bad_item(item):
        return None

    item = dict(item)
    item["title"] = clean(item.get("title", ""))
    item["text"] = strip_bad_lines(item.get("text", ""))
    item["summary"] = strip_bad_lines(item.get("summary", ""))

    if not item["summary"] and item["text"]:
        item["summary"] = item["text"][:260] + ("…" if len(item["text"]) > 260 else "")

    if looks_bad_item(item):
        return None
    if not item["text"] and not item.get("images"):
        return None
    return item

def remove_sinanjam_label():
    idx = OUT / "index.html"
    if not idx.exists():
        return
    s = idx.read_text(encoding="utf-8", errors="ignore")
    s = re.sub(r"\s*<small>\s*Sinanjam\s*</small>\s*", "\n", s, flags=re.I)
    s = re.sub(r"(?im)^\s*Sinanjam\s*$", "", s)
    idx.write_text(s, encoding="utf-8")

def main():
    if not ITEMS.exists():
        print(f"items.json yok: {ITEMS}")
        remove_sinanjam_label()
        return

    data = json.loads(ITEMS.read_text(encoding="utf-8"))
    cleaned = []
    removed = 0
    seen = set()

    for item in data:
        if not isinstance(item, dict):
            removed += 1
            continue
        c = clean_item(item)
        if c is None:
            removed += 1
            continue
        key = re.sub(r"\s+", " ", (c.get("title", "") + " " + c.get("summary", "")[:80]).lower()).strip()
        if key in seen:
            removed += 1
            continue
        seen.add(key)
        cleaned.append(c)

    ITEMS.write_text(json.dumps(cleaned, ensure_ascii=False, indent=2), encoding="utf-8")
    remove_sinanjam_label()
    print(f"Temiz içerik: {len(cleaned)} | Silinen bozuk/URL kayıt: {removed}")

if __name__ == "__main__":
    main()
