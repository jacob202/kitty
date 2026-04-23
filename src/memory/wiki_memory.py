#!/usr/bin/env python3
"""
Kitty Wiki Memory System
Based on Karpathy's LLM Wiki pattern - persistent, cross-linked markdown knowledge base
"""

import re
from datetime import datetime
from pathlib import Path
from typing import Any

# Project root - parent of src/
PROJECT_ROOT = Path(__file__).parent.parent.parent
WIKI_PATH = PROJECT_ROOT / "data" / "wiki"

FRONTMATTER_TEMPLATE = """---
title: {title}
created: {created}
updated: {updated}
type: {type}
tags: [{tags}]
sources: [{sources}]
---
"""

from dataclasses import dataclass


@dataclass
class WikiPage:
    """A single wiki page"""
    title: str
    path: Path
    page_type: str  # entity, concept, comparison, query, summary
    tags: list[str]
    content: str


class WikiMemory:
    """
    Kitty's LLM Wiki-based memory system
    - Structured markdown knowledge base with cross-links
    - Schema-defined conventions
    - Lint for health checks
    """

    def __init__(self, wiki_path: Path | None = None):
        self.wiki_path = wiki_path or WIKI_PATH
        self.schema = self._load_schema()

    def _load_schema(self) -> dict[str, Any]:
        """Load SCHEMA.md conventions"""
        schema_path = self.wiki_path / "SCHEMA.md"
        if schema_path.exists():
            return self._parse_schema(schema_path.read_text())
        return {}

    def _parse_schema(self, content: str) -> dict[str, Any]:
        """Parse schema markdown"""
        schema = {"tags": [], "conventions": []}

        in_tags = False
        for line in content.split("\n"):
            if line.strip() == "## Tag Taxonomy":
                in_tags = True
                continue
            if in_tags and line.startswith("## "):
                in_tags = False
            if in_tags and line.strip().startswith("- "):
                schema["tags"].append(line.strip()[2:])

        return schema

    def get_page(self, name: str) -> WikiPage | None:
        """Get a wiki page by name (without extension)"""
        for subdir in ["entities", "concepts", "comparisons", "queries"]:
            path = self.wiki_path / subdir / f"{name}.md"
            if path.exists():
                return self._read_page(path)
        return None

    def _read_page(self, path: Path) -> WikiPage:
        """Read a wiki page"""
        content = path.read_text()
        frontmatter, body = self._split_frontmatter(content)

        title = path.stem.replace("-", " ").title()
        page_type = "entity"
        tags = []

        if frontmatter:
            for line in frontmatter.split("\n"):
                if line.startswith("type: "):
                    page_type = line.split(": ")[1].strip()
                if line.startswith("tags: "):
                    tags = [t.strip() for t in line.split("[")[1].split("]")[0].split(",")]

        return WikiPage(title=title, path=path, page_type=page_type, tags=tags, content=body)

    def _split_frontmatter(self, content: str) -> tuple[str, str]:
        """Split frontmatter from body"""
        if content.startswith("---"):
            parts = content.split("---", 2)
            if len(parts) >= 3:
                return parts[1], parts[2].strip()
        return "", content

    def find_wikilinks(self, content: str) -> list[str]:
        """Find all [[wikilinks]] in content"""
        return re.findall(r"\[\[([^\]]+)\]\]", content)

    def find_backlinks(self, page_name: str) -> list[Path]:
        """Find pages that link to this page"""
        backlinks = []
        search_name = page_name.replace(" ", "-").lower()

        for subdir in ["entities", "concepts", "comparisons", "queries"]:
            dir_path = self.wiki_path / subdir
            if not dir_path.exists():
                continue
            for md_file in dir_path.glob("*.md"):
                content = md_file.read_text()
                if f"[[{search_name}]]" in content.lower():
                    backlinks.append(md_file)
        return backlinks

    def create_page(
        self,
        title: str,
        content: str,
        page_type: str = "entity",
        tags: list[str] = None,
        subdir: str = None
    ) -> Path:
        """Create a new wiki page"""
        if tags is None:
            tags = []
        if subdir is None:
            subdir = "entities" if page_type == "entity" else "concepts"

        filename = title.lower().replace(" ", "-") + ".md"
        path = self.wiki_path / subdir / filename

        now = datetime.now().strftime("%Y-%m-%d")
        frontmatter = FRONTMATTER_TEMPLATE.format(
            title=title,
            created=now,
            updated=now,
            type=page_type,
            tags=", ".join(tags),
            sources=""
        )

        path.write_text(frontmatter + "\n" + content)
        self._append_to_index(title, page_type, content.split("\n")[0][:80])
        self._append_to_log("create", title, [str(path)])

        return path

    def update_page(self, page: WikiPage, new_content: str) -> None:
        """Update existing page, bump updated date"""
        frontmatter, _ = self._split_frontmatter(page.path.read_text())

        now = datetime.now().strftime("%Y-%m-%d")
        updated_frontmatter = frontmatter.replace(
            f"updated: {page.content[:10]}" if "updated:" in frontmatter else "created:",
            f"updated: {now}"
        )
        page.path.write_text(updated_frontmatter + "\n" + new_content)
        self._append_to_log("update", page.title, [str(page.path)])

    def _append_to_index(self, title: str, page_type: str, summary: str) -> None:
        """Add page to index.md"""
        index_path = self.wiki_path / "index.md"
        content = index_path.read_text()

        section = f"## {page_type.title()}s\n"
        entry = f"- [[{title.lower().replace(' ', '-')}]] {summary}\n"

        if section in content:
            lines = content.split("\n")
            idx = next(i for i, line in enumerate(lines) if line == section.strip())
            lines.insert(idx + 1, entry)
            index_path.write_text("\n".join(lines))

    def _append_to_log(self, action: str, subject: str, files: list[str]) -> None:
        """Append action to log.md"""
        log_path = self.wiki_path / "log.md"
        now = datetime.now().strftime("%Y-%m-%d")
        entry = f"\n## [{now}] {action} | {subject}\n"
        if files:
            entry += "- " + "\n- ".join(files)

        log_path.write_text(log_path.read_text() + entry)

    def ingest(self, source: str, content: str, source_type: str = "article") -> list[Path]:
        """Ingest source and create/update wiki pages"""
        raw_dir = self.wiki_path / "raw" / source_type
        raw_dir.mkdir(parents=True, exist_ok=True)

        filename = f"{source[:50].lower().replace(' ', '-')}.md"
        (raw_dir / filename).write_text(content)

        created = []
        links = self.find_wikilinks(content)

        for link in links:
            existing = self.get_page(link.replace("[[", "").replace("]]", ""))
            if existing:
                self.update_page(existing, existing.content + "\n\n" + content)
            else:
                path = self.create_page(link, content)
                created.append(path)

        self._append_to_log("ingest", source, created)
        return created

    def lint(self) -> dict[str, list[str]]:
        """Lint wiki for issues"""
        issues = {
            "orphans": [],
            "broken_links": [],
            "missing_frontmatter": [],
            "stale": []
        }

        for subdir in ["entities", "concepts", "comparisons", "queries"]:
            dir_path = self.wiki_path / subdir
            if not dir_path.exists():
                continue

            for md_file in dir_path.glob("*.md"):
                content = md_file.read_text()

                frontmatter, body = self._split_frontmatter(content)
                if not frontmatter.strip():
                    issues["missing_frontmatter"].append(str(md_file))

                links = self.find_wikilinks(body)
                for link in links:
                    target = link.lower().replace(" ", "-")
                    if not self.get_page(target):
                        issues["broken_links"].append(f"{md_file.name} -> {link}")

                backlinks = self.find_backlinks(md_file.stem)
                if not backlinks and body.strip():
                    issues["orphans"].append(str(md_file))

        return issues

    def search(self, query: str) -> list[WikiPage]:
        """Search wiki pages"""
        results = []
        query_lower = query.lower()

        for subdir in ["entities", "concepts", "comparisons", "queries"]:
            dir_path = self.wiki_path / subdir
            if not dir_path.exists():
                continue
            for md_file in dir_path.glob("*.md"):
                if query_lower in md_file.stem.lower():
                    results.append(self._read_page(md_file))
                elif query_lower in md_file.read_text().lower():
                    results.append(self._read_page(md_file))

        return results


wiki_memory = WikiMemory()
