"""
scripts/enrich_pageindex.py
===========================
PageIndex 节点内容填充工具

从 CCAR-33-R2_Full.md 提取每篇条款的原文，
写入 data/processed/CCAR-33-R2_structure.json 的 text 字段。

运行:
    python scripts/enrich_pageindex.py [--dry-run]

验收条件:
  - 每个叶节点的 text 字段不为空
  - 共 >= 40 个节点拥有 text 内容
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).parent.parent

STRUCTURE_JSON = ROOT / "data/processed/CCAR-33-R2_structure.json"
FULL_MD = ROOT / "data/processed/CCAR-33-R2_Full.md"
CHAPTERS_DIR = ROOT / "data/processed/CCAR-33-R2_chapters"


# ── Step 1: parse markdown files into article_map ────────────────────────────

def parse_markdown_articles(md_path: Path) -> dict[str, str]:
    """
    Parse a markdown file and return a dict:
        "33.1"  → full article text (title + body)
        "33.27" → ...
    Handles both ## and ### headings.
    """
    content = md_path.read_text(encoding="utf-8")

    # Split on ## or ### headings
    chunks = re.split(r'^(#{2,3} .+)$', content, flags=re.MULTILINE)

    article_map: dict[str, str] = {}
    i = 0
    while i < len(chunks):
        chunk = chunks[i].strip()
        if re.match(r'^#{2,3} ', chunk):
            title = re.sub(r'^#{2,3} ', '', chunk).strip()
            body = chunks[i + 1].strip() if i + 1 < len(chunks) else ""
            article_match = re.search(r'第(33\.\d+)条', title)
            if article_match:
                article_num = article_match.group(1)
                # Build full text: "第33.X条 名称\n\n正文内容"
                full_text = title + "\n\n" + body if body else title
                # Only overwrite if richer content available
                existing = article_map.get(article_num, "")
                if len(full_text) > len(existing):
                    article_map[article_num] = full_text
            i += 2
        else:
            i += 1

    return article_map


def build_article_map() -> dict[str, str]:
    """Merge article maps from Full.md and all chapter markdown files."""
    merged: dict[str, str] = {}

    # Parse main Full.md
    if FULL_MD.exists():
        merged.update(parse_markdown_articles(FULL_MD))

    # Parse chapter files (richer content)
    if CHAPTERS_DIR.exists():
        for md_file in sorted(CHAPTERS_DIR.glob("*.md")):
            chapter_map = parse_markdown_articles(md_file)
            for k, v in chapter_map.items():
                existing = merged.get(k, "")
                if len(v) > len(existing):
                    merged[k] = v

    return merged


# ── Step 2: flatten & enrich structure nodes ─────────────────────────────────

def flatten_nodes(nodes: list[dict]) -> list[dict]:
    result = []
    for n in nodes:
        result.append(n)
        result.extend(flatten_nodes(n.get("nodes", [])))
    return result


def enrich_node(node: dict, article_map: dict[str, str]) -> bool:
    """
    Fill ``text`` field of a node if it is empty.
    Returns True if the node was enriched.
    """
    if node.get("text"):
        return False  # already has text

    # Strategy 1: join content_parts
    content_parts = node.get("content_parts", [])
    if content_parts:
        node["text"] = "\n\n".join(content_parts)
        return True

    # Strategy 2: match article number from title → markdown text
    title = node.get("title", "")
    m = re.search(r'第(33\.\d+)条', title)
    if m:
        article_num = m.group(1)
        if article_num in article_map:
            node["text"] = article_map[article_num]
            return True

    # Strategy 3: extract embedded body from title
    # Title format: "第33.X条 ArticleName （a）body text..."
    m2 = re.match(
        r'第\d+(?:\.\d+)?条\s+[\u4e00-\u9fff\s「」、，。：；—]+\s+([\s\S]+)',
        title,
    )
    if m2:
        embedded = m2.group(1).strip()
        if len(embedded) > 10:
            node["text"] = embedded
            return True

    return False


# ── Main ─────────────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(description="PageIndex content enrichment")
    parser.add_argument("--dry-run", action="store_true", help="Show stats without writing")
    args = parser.parse_args()

    print(f"📂 Structure JSON : {STRUCTURE_JSON}")
    print(f"📂 Full markdown  : {FULL_MD}")

    if not STRUCTURE_JSON.exists():
        sys.exit(f"❌ Not found: {STRUCTURE_JSON}")
    if not FULL_MD.exists():
        sys.exit(f"❌ Not found: {FULL_MD}")

    data = json.loads(STRUCTURE_JSON.read_text(encoding="utf-8"))
    article_map = build_article_map()
    print(f"✅ Parsed {len(article_map)} articles from markdown + chapter files")

    all_nodes = flatten_nodes(data["structure"])
    print(f"✅ Loaded {len(all_nodes)} total nodes")

    before = sum(1 for n in all_nodes if n.get("text"))
    enriched = 0
    for node in all_nodes:
        if enrich_node(node, article_map):
            enriched += 1

    after = sum(1 for n in all_nodes if n.get("text"))

    print(f"\n📊 Results:")
    print(f"   Before: {before}/{len(all_nodes)} nodes with text")
    print(f"   Enriched: +{enriched} nodes")
    print(f"   After : {after}/{len(all_nodes)} nodes with text")

    # Acceptance check
    leaf_nodes = [n for n in all_nodes if not n.get("nodes")]
    leaf_with_text = sum(1 for n in leaf_nodes if n.get("text"))
    print(f"\n   Leaf nodes: {leaf_with_text}/{len(leaf_nodes)} have text")

    if args.dry_run:
        print("\n[DRY RUN] Not writing changes.")
        return

    STRUCTURE_JSON.write_text(
        json.dumps(data, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(f"\n✅ Saved enriched structure → {STRUCTURE_JSON}")

    # Final acceptance check
    if after < 40:
        print(f"⚠️  WARNING: Only {after} nodes have text. Target is >= 40.")
        sys.exit(1)
    print(f"✅ Acceptance: {after} nodes with text (>= 40 required)")


if __name__ == "__main__":
    main()
