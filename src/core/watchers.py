import queue
import subprocess
import sys
import threading
import time
from pathlib import Path

from rich.console import Console

console = Console()

class FolderWatcher(threading.Thread):
    """Watches ./manuals for new PDFs/EPUBs and auto-ingests them."""
    def __init__(self, path=None, interval=8, store=None):
        super().__init__(daemon=True)
        if path is None:
            import json
            _config_path = Path(__file__).parent.parent.parent / "data" / "config" / "kitty_config.json"
            _config = json.loads(_config_path.read_text())
            path = Path(_config["watch_paths"]["manuals"]).expanduser()
        self.path = Path(path)
        self.path.mkdir(parents=True, exist_ok=True)
        self.interval = interval
        self._seen = set()
        self._store = store

    def run(self):
        text_exts = {".txt", ".md"}
        doc_exts = {".pdf", ".epub"}
        if self.path.exists():
            self._seen = set(self.path.rglob("*"))
        while True:
            time.sleep(self.interval)
            if not self.path.exists():
                continue
            current = set(self.path.rglob("*"))
            new = {f for f in current - self._seen if f.is_file()}
            for f in new:
                console.print(f"\n[cyan]📄 New file detected: {f.name}[/cyan]")
                if f.suffix.lower() in text_exts and self._store:
                    try:
                        text = f.read_text(errors="ignore")
                        self._store.add_document(text, metadata={"source": str(f), "type": "manual"})
                        console.print(f"[green]✓ {f.name} ingested into LightRAG.[/green]")
                    except Exception as e:
                        console.print(f"[yellow]⚠ LightRAG ingest failed for {f.name}: {e}[/yellow]")
                elif f.suffix.lower() in doc_exts:
                    r = subprocess.run(
                        [sys.executable, "ingest_manuals.py", str(f)],
                        capture_output=True, text=True,
                    )
                    if r.returncode == 0:
                        console.print(f"[green]✓ {f.name} ingested.[/green]")
                    else:
                        console.print(f"[yellow]⚠ Ingest failed for {f.name}[/yellow]")
            self._seen = current


_VOICE_FILE = Path("/tmp/kitty_voice.txt")


# ── Voice watcher ───────────────────────────────────────────────────────────────
class VoiceWatcher(threading.Thread):
    """Watches for voice input via file drop.
    MacWhisper must run this after-transcription script:
        echo \"$transcription\" > /tmp/kitty_voice.txt
    In MacWhisper: Settings → After Transcription → Run Shell Script
    """
    def __init__(self, q: queue.Queue, interval: float = 0.4):
        super().__init__(daemon=True)
        self.queue         = q
        self.interval      = interval
        self.enabled       = False
        self._last_clip    = ""   # last seen clipboard content

    @staticmethod
    def _read_clipboard() -> str:
        try:
            r = subprocess.run(["pbpaste"], capture_output=True, text=True)
            return r.stdout.strip()
        except Exception:
            return ""

    def arm_clipboard(self):
        """Snapshot current clipboard so next change is treated as voice input."""
        self._last_clip = self._read_clipboard()

    def run(self):
        while True:
            time.sleep(self.interval)
            # Method 1: file drop always works — no need to toggle /voice
            if _VOICE_FILE.exists():
                try:
                    text = _VOICE_FILE.read_text(errors="ignore").strip()
                    _VOICE_FILE.unlink(missing_ok=True)
                    # Reject binary blobs: require mostly printable ASCII/UTF-8
                    printable = sum(1 for c in text if c.isprintable() or c in "\n\t")
                    if text and len(text) > 0 and (printable / len(text)) > 0.85:
                        self.queue.put(text)
                    continue
                except Exception:
                    pass
            # Clipboard method disabled — was picking up clipboard manager history
            # File drop (/tmp/kitty_voice.txt) is the only supported voice method


# ── Desktop/AirDrop photo watcher ───────────────────────────────────────────────
class DesktopPhotoWatcher(threading.Thread):
    """Watches ~/Desktop for new images (AirDrop from iPhone lands here)."""
    def __init__(self, q: queue.Queue, interval: float = 3.0):
        super().__init__(daemon=True)
        self.queue    = q
        self.interval = interval
        self._seen: set = set()

    def run(self):
        desktop  = Path.home() / "Desktop"
        img_exts = {".jpg", ".jpeg", ".png", ".heic", ".heif", ".gif", ".webp"}
        try:
            if desktop.exists():
                self._seen = {f for f in desktop.iterdir()
                              if f.is_file() and f.suffix.lower() in img_exts}
        except (PermissionError, OSError):
            pass
        while True:
            time.sleep(self.interval)
            try:
                if not desktop.exists():
                    continue
                current = {f for f in desktop.iterdir()
                           if f.is_file() and f.suffix.lower() in img_exts}
                for f in current - self._seen:
                    try:
                        if time.time() - f.stat().st_mtime < 45:
                            self.queue.put(f)
                    except (PermissionError, OSError):
                        pass
                self._seen = current
            except (PermissionError, OSError):
                pass


# ── Fabric-style patterns ────────────────────────────────────────────────────────
