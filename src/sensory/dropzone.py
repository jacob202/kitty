import asyncio
import glob
import os
from pathlib import Path


class ICloudDropzone:
    """
    Monitors a dedicated iCloud Drive folder to bridge the gap between
    the user's mobile phone and Kitty's local macOS execution environment.
    Uses asyncio.sleep() instead of time.sleep() to avoid blocking the event loop.
    """

    def __init__(self, folder_name="Kitty_Drop"):
        self.icloud_base = os.path.expanduser("~/Library/Mobile Documents/com~apple~CloudDocs")
        self.dropzone_path = os.path.join(self.icloud_base, folder_name)
        if not os.path.exists(self.dropzone_path):
            os.makedirs(self.dropzone_path)
            print(f"[System] Created new iCloud Dropzone at: {self.dropzone_path}")

    async def _is_file_stable_async(self, filepath: str, wait_ms: int = 500) -> bool:
        """
        Async file stability check using asyncio.sleep() — critical for M1 8GB.
        Rejects iCloud placeholder files (.icloud suffix or dot-prefixed).
        Two stat calls separated by wait_ms confirms file is fully synced.
        """
        path = Path(filepath)
        # Reject iCloud placeholders that haven't synced yet
        if path.suffix.lower() == ".icloud" or path.name.startswith("."):
            return False
        try:
            stat1 = os.stat(filepath)
        except FileNotFoundError:
            return False
        # Non-blocking wait — does NOT freeze the event loop
        await asyncio.sleep(wait_ms / 1000.0)
        try:
            stat2 = os.stat(filepath)
        except FileNotFoundError:
            return False
        return stat1.st_size == stat2.st_size and stat1.st_size > 0

    async def get_latest_file_async(self, extension_filter=None, max_wait_seconds: int = 10) -> str:
        """
        Async version: polls for a stable file, yields control between checks.
        Raises FileNotFoundError if no stable file appears within max_wait_seconds.
        """
        start = asyncio.get_event_loop().time()
        while True:
            files = glob.glob(f"{self.dropzone_path}/*")
            if extension_filter:
                files = [f for f in files if Path(f).suffix.lower() in extension_filter]
            if files:
                files.sort(key=os.path.getmtime, reverse=True)
                for candidate in files[:3]:
                    if await self._is_file_stable_async(candidate):
                        return candidate
            elapsed = asyncio.get_event_loop().time() - start
            if elapsed > max_wait_seconds:
                raise FileNotFoundError(
                    f"No stable file found in dropzone after {max_wait_seconds}s"
                )
            await asyncio.sleep(0.5)

    def get_latest_file(self, extension_filter=None) -> str:
        """
        Synchronous fallback for legacy callers and testing.
        Grabs the most recently modified file matching the extension filter.
        """
        files = glob.glob(f"{self.dropzone_path}/*")
        if extension_filter:
            files = [f for f in files if Path(f).suffix.lower() in extension_filter]
        if not files:
            raise FileNotFoundError("The iCloud Dropzone is currently empty.")
        return max(files, key=os.path.getmtime)
