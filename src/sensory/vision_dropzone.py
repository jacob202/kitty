import asyncio
import base64
import os

from src.sensory.dropzone import ICloudDropzone


class VisionIngestionPipeline:
    """
    Fetches the latest image from iCloud, normalizes Apple's HEIC format,
    and prepares it for multi-modal LLM analysis.
    """

    def __init__(self):
        self.dropzone = ICloudDropzone("Kitty_Drop")
        self.temp_dir = "/tmp/kitty_vision"
        if not os.path.exists(self.temp_dir):
            os.makedirs(self.temp_dir)

    async def fetch_and_encode(self) -> dict:
        latest_image = self.dropzone.get_latest_file(
            extension_filter=[".heic", ".jpg", ".jpeg", ".png"]
        )
        print(f"[System] 👁️ Fetched visual data: {os.path.basename(latest_image)}")
        normalized_path = await self._normalize_to_jpeg(latest_image)
        base64_data = self._encode_image(normalized_path)
        if normalized_path != latest_image and os.path.exists(normalized_path):
            os.remove(normalized_path)
        return {
            "mime_type": "image/jpeg",
            "data": base64_data,
            "source_file": os.path.basename(latest_image),
        }

    async def _normalize_to_jpeg(self, input_path: str) -> str:
        if input_path.lower().endswith((".jpg", ".jpeg")):
            return input_path
        output_path = os.path.join(self.temp_dir, "normalized_vision.jpg")
        cmd = ["sips", "-s", "format", "jpeg", "-Z", "1600", input_path, "--out", output_path]
        process = await asyncio.create_subprocess_exec(
            *cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
        )
        await process.communicate()
        if process.returncode != 0:
            raise Exception("Failed to convert image format using sips.")
        return output_path

    def _encode_image(self, image_path: str) -> str:
        with open(image_path, "rb") as image_file:
            return base64.b64encode(image_file.read()).decode("utf-8")
