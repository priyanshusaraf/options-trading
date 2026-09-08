#!/usr/bin/env python3
"""Extract the main `#content` text from cached first-party HTML.

This utility is for review convenience. It does not infer review state or alter the
crawl inventory.
"""

from __future__ import annotations

import argparse
from html.parser import HTMLParser
import json
from pathlib import Path


BLOCKS = {"h1", "h2", "h3", "h4", "p", "li", "pre", "blockquote", "dt", "dd", "caption", "th", "td"}


class ContentParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.active = False
        self.depth = 0
        self.block: str | None = None
        self.parts: list[str] = []
        self.lines: list[str] = []
        self.skip = 0

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        values = dict(attrs)
        if not self.active and tag == "div" and values.get("id") == "content":
            self.active = True
            self.depth = 1
            return
        if not self.active:
            return
        if tag == "div":
            self.depth += 1
            if values.get("class") == "mailing-list-signup":
                self.skip += 1
        if self.skip:
            return
        if tag in BLOCKS:
            self._flush()
            self.block = tag

    def handle_endtag(self, tag: str) -> None:
        if not self.active:
            return
        if tag in BLOCKS and not self.skip:
            self._flush()
            self.block = None
        if tag == "div":
            if self.skip:
                self.skip -= 1
            self.depth -= 1
            if self.depth == 0:
                self._flush()
                self.active = False

    def handle_data(self, data: str) -> None:
        if self.active and not self.skip and self.block:
            text = " ".join(data.split())
            if text:
                self.parts.append(text)

    def _flush(self) -> None:
        if self.parts:
            prefix = "## " if self.block in {"h1", "h2", "h3", "h4"} else "- " if self.block == "li" else ""
            self.lines.append(prefix + " ".join(self.parts))
            self.parts = []


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--inventory", required=True, type=Path)
    parser.add_argument("--cache", required=True, type=Path)
    parser.add_argument("urls", nargs="+")
    args = parser.parse_args()
    inventory = json.loads(args.inventory.read_text(encoding="utf-8"))
    for url in args.urls:
        row = inventory[url]
        article = ContentParser()
        article.feed((args.cache / row["checksum"]).read_text(encoding="utf-8", errors="replace"))
        print(f"\n===== SOURCE {url} SHA256 {row['checksum']} =====\n")
        print("\n\n".join(article.lines))


if __name__ == "__main__":
    main()
