import glob
from pathlib import Path


class ObsidianBridge:
    def __init__(self, vault_path):
        self.vault_path = vault_path

    def search_notes(self, query):
        results = []
        search_pattern = str(Path(self.vault_path) / "**/*.md")
        for md_file in glob.glob(search_pattern, recursive=True):
            try:
                with open(md_file, encoding='utf-8') as f:
                    content = f.read()
                    if query.lower() in content.lower():
                        results.append({"file": md_file, "snippet": content[:200]})
            except Exception:
                pass
        return results
