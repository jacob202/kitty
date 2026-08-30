"""Deployment Agent — deploy projects to hosting platforms.

Public API:
  deploy(target_dir, platform, config) -> dict
  get_status(deploy_id) -> dict
"""
from __future__ import annotations

import logging
from pathlib import Path

logger = logging.getLogger("kitty.deploy")

SUPPORTED_PLATFORMS = ["vercel", "netlify", "github-pages", "docker"]


async def deploy(
    target_dir: str,
    platform: str = "docker",
    config: dict | None = None,
) -> dict:
    """Deploy a project to the specified platform."""
    if platform not in SUPPORTED_PLATFORMS:
        return {"error": f"Unsupported platform: {platform}. Supported: {SUPPORTED_PLATFORMS}"}

    path = Path(target_dir)
    if not path.exists():
        return {"error": f"Target directory not found: {target_dir}"}

    if platform == "docker":
        return await _deploy_docker(path, config or {})
    elif platform == "github-pages":
        return await _deploy_github_pages(path, config or {})
    else:
        return {
            "platform": platform,
            "status": "ready",
            "message": f"Ready to deploy to {platform}. Run the platform CLI manually.",
            "target_dir": str(path),
        }


async def _deploy_docker(path: Path, config: dict) -> dict:
    dockerfile = path / "Dockerfile"
    if not dockerfile.exists():
        dockerfile.write_text(
            "FROM python:3.12-slim\n"
            "WORKDIR /app\n"
            "COPY . .\n"
            'CMD ["python", "app.py"]\n'
        )

    return {
        "platform": "docker",
        "status": "dockerfile_ready",
        "message": "Dockerfile created. Run: docker build -t app . && docker run app",
        "dockerfile_path": str(dockerfile),
    }


async def _deploy_github_pages(path: Path, config: dict) -> dict:
    return {
        "platform": "github-pages",
        "status": "ready",
        "message": "Push to GitHub and enable Pages in repo settings.",
        "target_dir": str(path),
    }
