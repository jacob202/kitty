# Kitty AI Tools

This directory contains external binaries and tools used by the Kitty AI project.

## Real-ESRGAN (Image Upscaling)

**Location**: `tools/realesrgan-ncnn-vulkan`

Real-ESRGAN is a neural network-based image upscaling tool optimized for electronics schematics and PCB photos.

### Setup Instructions

1. **Verify binary exists**:
   ```bash
   ls -la tools/realesrgan-ncnn-vulkan
   ```

2. **Make executable** (if not already):
   ```bash
   chmod +x tools/realesrgan-ncnn-vulkan
   ```

3. **Verify it works**:
   ```bash
   ./tools/realesrgan-ncnn-vulkan --help
   ```

### Usage

The binary is automatically used by `kitty_modules/schematic_analyzer.py` when upscaling schematic images:

```python
from kitty_modules.schematic_analyzer import SchematicAnalyzer

analyzer = SchematicAnalyzer()
upscaled_path = analyzer.upscale_image("schematic.png")
```

### Available Models

1. `realesrgan-x4plus` (default) - General purpose
2. `realesrgan-x4plus-anime` - Enhanced for diagrams
3. `realesrgan-animevideov3` - For video frames

### macOS Notes

If macOS blocks the binary due to security restrictions:

1. Go to **System Preferences > Security & Privacy**
2. Click the **General** tab
3. Click **Open Anyway** next to the blocked app message

Or disable Gatekeeper temporarily:
```bash
sudo spctl --master-disable
```

## Directory Structure

```
tools/
├── README.md                    # This file
├── realesrgan-ncnn-vulkan       # Binary executable
├── data/models/                      # Model files for Real-ESRGAN
│   ├── realesrgan-x4plus.bin
│   ├── realesrgan-x4plus.param
│   └── ...
└── ...
```

## Troubleshooting

### Binary not found error
Ensure the binary is at `tools/realesrgan-ncnn-vulkan` and has executable permissions.

### Permission denied
Run `chmod +x tools/realesrgan-ncnn-vulkan`

### macOS security block
Follow the instructions above or run: `sudo spctl --master-disable`

### Slow upscaling
The first run may be slow as models are loaded. Subsequent runs are faster.

## Performance

- Image upscaling typically takes 2-10 seconds depending on image size
- 4K images may take up to 30 seconds
- Falls back to PIL-based upscaling if Real-ESRGAN fails

## Credits

Real-ESRGAN by [Xintao Wang](https://github.com/xinntao/Real-ESRGAN)
Binary built with [ncnn](https://github.com/Tencent/ncnn) by nihui
