# Real-ESRGAN-ncnn-vulkan macOS ARM64 Setup Guide

## Quick Setup (Manual Commands)

Run these commands in your terminal:

```bash
# 1. Navigate to the tools directory
cd /Users/jacobbrizinski/AgentCompany/tools

# 2. Download the latest macOS ARM64 release
curl -L -o realesrgan-ncnn-vulkan-macos-arm64.zip \
  "https://github.com/xinntao/Real-ESRGAN/releases/download/v0.2.0/realesrgan-ncnn-vulkan-v0.2.0-macos-arm64.zip"

# 3. Extract the archive
unzip -o realesrgan-ncnn-vulkan-macos-arm64.zip

# 4. Move to target directory
mv realesrgan-ncnn-vulkan-v0.2.0-macos-arm64 realesrgan-ncnn-vulkan

# 5. Make executable
chmod +x realesrgan-ncnn-vulkan/realesrgan-ncnn-vulkan

# 6. Verify installation
ls -lh realesrgan-ncnn-vulkan/realesrgan-ncnn-vulkan

# 7. Test binary
./realesrgan-ncnn-vulkan/realesrgan-ncnn-vulkan --help

# 8. Create a test image (requires Python with PIL)
python3 << 'EOF'
from PIL import Image
img = Image.new('RGB', (100, 100), color='red')
img.save('test_input.png')
print("Test image created")
EOF

# 9. Test upscaling
cd realesrgan-ncnn-vulkan
./realesrgan-ncnn-vulkan -i test_input.png -o test_output.png -n realesrgan-x4plus
```

## Alternative: Run the Setup Script

```bash
chmod +x /Users/jacobbrizinski/AgentCompany/setup_realesrgan.sh
bash /Users/jacobbrizinski/AgentCompany/setup_realesrgan.sh
```

## Binary Information

- **Version**: v0.2.0
- **Source**: https://github.com/xinntao/Real-ESRGAN/releases
- **Target Path**: `/Users/jacobbrizinski/AgentCompany/tools/realesrgan-ncnn-vulkan/`
- **Binary Path**: `/Users/jacobbrizinski/AgentCompany/tools/realesrgan-ncnn-vulkan/realesrgan-ncnn-vulkan`

## Usage Examples

```bash
# Basic upscaling 4x
./realesrgan-ncnn-vulkan -i input.png -o output.png -n realesrgan-x4plus

# Upscaling with specific model
./realesrgan-ncnn-vulkan -i input.jpg -o output.jpg -n realesrgan-x4plus-anime

# Process multiple images
./realesrgan-ncnn-vulkan -i input_folder -o output_folder -n realesrgan-x4plus
```

## Available Models

The binary should include these pre-trained models:
- `realesrgan-x4plus` - General photos (4x upscaling)
- `realesrgan-x4plus-anime` - Anime-style images (4x upscaling)
- `realesrnet-x4plus` - Alternative general model

Models are typically located in the `data/models/` subdirectory.

## Troubleshooting

1. **"Permission denied"**: Run `chmod +x realesrgan-ncnn-vulkan`
2. **"Command not found"**: Use the full path or add to PATH
3. **Missing models**: Download models from the GitHub releases page
4. **Library issues**: Ensure Vulkan SDK is installed on macOS

## Verification Checklist

- [ ] Binary exists at `tools/realesrgan-ncnn-vulkan/realesrgan-ncnn-vulkan`
- [ ] Binary has executable permissions (`chmod +x`)
- [ ] Binary returns help text when run with `--help`
- [ ] Can successfully upscale a test image
