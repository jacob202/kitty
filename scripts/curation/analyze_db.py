
import sqlite3
from pathlib import Path
from collections import defaultdict
import json

def analyze_db(db_path, books_dir):
    """
    Analyzes the OpenWebUI database and generates a summary report.
    """
    if not db_path.exists():
        print(f"Database file not found: {db_path}")
        return

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    # Get all knowledge bases
    cursor.execute("SELECT id, name FROM knowledge")
    kbs = {id: {"name": name, "files": []} for id, name in cursor.fetchall()}

    # Get all files and their knowledge base assignments
    cursor.execute("SELECT file.id, file.filename, file.data, knowledge_file.knowledge_id FROM file JOIN knowledge_file ON file.id = knowledge_file.file_id")
    for file_id, filename, data, kb_id in cursor.fetchall():
        if kb_id in kbs:
            kbs[kb_id]["files"].append({"id": file_id, "filename": filename, "data": data})

    conn.close()

    # Get a list of all files in the books directory
    book_files = {p.name for p in books_dir.rglob('*') if p.is_file()}

    # Generate the report
    for kb_id, kb_data in kbs.items():
        print(f"--- Knowledge Base: {kb_data['name']} ---")
        total_files = len(kb_data["files"])
        files_with_content = 0
        empty_files = 0
        orphaned_files = 0

        for file_info in kb_data["files"]:
            # Check for content
            has_content = True
            if file_info["data"]:
                try:
                    file_data = json.loads(file_info["data"])
                    if file_data.get("status") == "error" and "content provided is empty" in file_data.get("message", ""):
                        has_content = False
                except (json.JSONDecodeError, TypeError):
                    pass
            
            if has_content:
                files_with_content += 1
            else:
                empty_files += 1

            # Check if orphaned
            if file_info["filename"] not in book_files:
                orphaned_files += 1
        
        print(f"Total files: {total_files}")
        print(f"Files with content: {files_with_content}")
        print(f"Empty or unprocessed files: {empty_files}")
        print(f"Orphaned files (in DB but not in Books folder): {orphaned_files}")
        print()

if __name__ == "__main__":
    DEFAULT_DB = Path.home() / "kitty-services/open-webui-data/webui.db"
    BOOKS_DIR = Path("/Volumes/DATA/books")
    analyze_db(DEFAULT_DB, BOOKS_DIR)
